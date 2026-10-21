//go:build windows

// WARDOGS helper: Windows process-loopback audio -> raw 48kHz/2ch/s16le on stdout.
// No game memory access, injection, device-routing changes or recording to disk.
// Built using the Go standard library for a redistributable standalone Windows exe.
package main

import (
 "fmt"
 "os"
 "runtime"
 "strconv"
 "sync/atomic"
 "syscall"
 "time"
 "unsafe"
)

type guid struct { a uint32; b,c uint16; d [8]byte }
type waveFormat struct { tag uint16; channels uint16; sampleRate uint32; avgBytes uint32; blockAlign uint16; bits uint16; cbSize uint16 }
type activation struct { kind uint32; pid uint32; mode uint32 }
type propVariantBlob struct { typ uint16; reserved1, reserved2, reserved3 uint16; size uint32; padding uint32; data uintptr }
type handlerVtbl struct { query, add, release, completed uintptr }
type handler struct { vtbl *handlerVtbl; refs int32; event uintptr }

var (
 iidIUnknown = guid{0,0,0,[8]byte{0xc0,0,0,0,0,0,0,0x46}}
 iidAgile = guid{0x94ea2b94,0xe9cc,0x49e0,[8]byte{0xc0,0xff,0xee,0x64,0xca,0x8f,0x5b,0x90}}
 iidCompletion = guid{0x41d949ab,0x9862,0x444a,[8]byte{0x80,0xf6,0xc2,0x61,0x33,0x4d,0xa5,0xeb}}
 iidAudioClient = guid{0x1cb9ad4c,0xdbfa,0x4c32,[8]byte{0xb1,0x78,0xc2,0xf5,0x68,0xa7,0x03,0xb2}}
 iidAudioCapture = guid{0xc8adbd64,0xe71e,0x48a0,[8]byte{0xa4,0xde,0x18,0x5c,0x39,0x5c,0xd3,0x17}}
 ole32 = syscall.NewLazyDLL("ole32.dll")
 mmdevapi = syscall.NewLazyDLL("Mmdevapi.dll")
 kernel = syscall.NewLazyDLL("kernel32.dll")
 coInit = ole32.NewProc("CoInitializeEx")
 coUninit = ole32.NewProc("CoUninitialize")
 activateAsync = mmdevapi.NewProc("ActivateAudioInterfaceAsync")
 createEvent = kernel.NewProc("CreateEventW")
 setEvent = kernel.NewProc("SetEvent")
 closeHandle = kernel.NewProc("CloseHandle")
 waitObject = kernel.NewProc("WaitForSingleObject")
 openProcess = kernel.NewProc("OpenProcess")
 vtbl handlerVtbl
)

func equalGUID(a,b *guid) bool { return *a==*b }
func query(ptr, id, out uintptr) uintptr {
 if out==0 { return 0x80004003 } // E_POINTER
 *(*uintptr)(unsafe.Pointer(out)) = 0
 if id==0 || ptr==0 { return 0x80004002 }
 g := (*guid)(unsafe.Pointer(id))
 if equalGUID(g,&iidIUnknown)||equalGUID(g,&iidCompletion)||equalGUID(g,&iidAgile) {
  *(*uintptr)(unsafe.Pointer(out))=ptr
  atomic.AddInt32(&(*handler)(unsafe.Pointer(ptr)).refs,1)
  return 0
 }
 return 0x80004002 // E_NOINTERFACE
}
func addRef(ptr uintptr) uintptr { return uintptr(atomic.AddInt32(&(*handler)(unsafe.Pointer(ptr)).refs,1)) }
func release(ptr uintptr) uintptr { return uintptr(atomic.AddInt32(&(*handler)(unsafe.Pointer(ptr)).refs,-1)) }
func completed(ptr, operation uintptr) uintptr {
 if ptr!=0 { setEvent.Call((*handler)(unsafe.Pointer(ptr)).event) }
 return 0
}
func init() {
 vtbl=handlerVtbl{syscall.NewCallback(query),syscall.NewCallback(addRef),syscall.NewCallback(release),syscall.NewCallback(completed)}
}
func hrCheck(v uintptr, name string) error {
 if uint32(v)&0x80000000!=0 { return fmt.Errorf("%s HRESULT 0x%08X",name,uint32(v)) }
 return nil
}
func invoke(object uintptr, method int, args ...uintptr) uintptr {
 if object==0 { panic("null COM object") }
 vptr:=*(*uintptr)(unsafe.Pointer(object))
 fn:=*(*uintptr)(unsafe.Pointer(vptr+uintptr(method)*unsafe.Sizeof(uintptr(0))))
 parameters:=append([]uintptr{object},args...)
 result,_,_:=syscall.SyscallN(fn,parameters...)
 return result
}
func releaseCOM(object uintptr) { if object!=0 { invoke(object,2) } }
func winWait(handle uintptr, timeout uint32) uint32 { ret,_,_:=waitObject.Call(handle,uintptr(timeout)); return uint32(ret) }
func run(pid uint32) error {
 runtime.LockOSThread()
 defer runtime.UnlockOSThread()
 v,_,_:=coInit.Call(0,0)
 if err:=hrCheck(v,"CoInitializeEx");err!=nil {return err}
 defer coUninit.Call()
 evt,_,err:=createEvent.Call(0,0,0,0)
 if evt==0 {return fmt.Errorf("CreateEventW: %v",err)}
 defer closeHandle.Call(evt)
 h:=&handler{vtbl:&vtbl,refs:1,event:evt}
 params:=activation{kind:1,pid:pid,mode:0}
 variant:=propVariantBlob{typ:0x41,size:uint32(unsafe.Sizeof(params)),data:uintptr(unsafe.Pointer(&params))}
 name,_:=syscall.UTF16PtrFromString("VAD\\Process_Loopback")
 var operation uintptr
 v,_,_ = activateAsync.Call(uintptr(unsafe.Pointer(name)),uintptr(unsafe.Pointer(&iidAudioClient)),uintptr(unsafe.Pointer(&variant)),uintptr(unsafe.Pointer(h)),uintptr(unsafe.Pointer(&operation)))
 runtime.KeepAlive(name)
 runtime.KeepAlive(params)
 runtime.KeepAlive(variant)
 if err:=hrCheck(v,"ActivateAudioInterfaceAsync");err!=nil {return err}
 defer releaseCOM(operation)
 if winWait(evt,10000)!=0 {return fmt.Errorf("process loopback activation timed out")}
 var activationHR int32
 var client uintptr
 v=invoke(operation,3,uintptr(unsafe.Pointer(&activationHR)),uintptr(unsafe.Pointer(&client)))
 if err:=hrCheck(v,"GetActivateResult");err!=nil {return err}
 if err:=hrCheck(uintptr(uint32(activationHR)),"AudioClient activation");err!=nil {return err}
 if client==0 {return fmt.Errorf("audio client is null")}
 defer releaseCOM(client)
 // 2 channels x 16-bit x 48000 Hz. 192000 bytes/sec.
 format:=waveFormat{tag:1,channels:2,sampleRate:48000,avgBytes:192000,blockAlign:4,bits:16,cbSize:0}
 const streamFlags = 0x00020000 | 0x80000000 // LOOPBACK | AUTOCONVERTPCM
 v=invoke(client,3,0,streamFlags,0,0,uintptr(unsafe.Pointer(&format)),0)
 if err:=hrCheck(v,"IAudioClient.Initialize");err!=nil {return err}
 var capture uintptr
 v=invoke(client,14,uintptr(unsafe.Pointer(&iidAudioCapture)),uintptr(unsafe.Pointer(&capture)))
 if err:=hrCheck(v,"IAudioClient.GetService");err!=nil {return err}
 if capture==0{return fmt.Errorf("capture client is null")}
 defer releaseCOM(capture)
 v=invoke(client,10)
 if err:=hrCheck(v,"IAudioClient.Start");err!=nil{return err}
 defer invoke(client,11)
 fmt.Fprintln(os.Stderr,"READY 48000 2 s16le")
 process,_,_:=openProcess.Call(0x00100000,0,uintptr(pid))
 if process!=0 {defer closeHandle.Call(process)}
 silence:=make([]byte,5760)
 lastData:=time.Now()
 for {
  if process!=0 && winWait(process,0)==0 {return nil}
  time.Sleep(10*time.Millisecond)
  var available uint32
  v=invoke(capture,5,uintptr(unsafe.Pointer(&available)))
  if err:=hrCheck(v,"GetNextPacketSize");err!=nil{return err}
  got:=false
  for available!=0 {
   var data uintptr; var frames uint32; var flags uint32
   v=invoke(capture,3,uintptr(unsafe.Pointer(&data)),uintptr(unsafe.Pointer(&frames)),uintptr(unsafe.Pointer(&flags)),0,0)
   if err:=hrCheck(v,"GetBuffer");err!=nil{return err}
   n:=int(frames)*4
   if n>0 {
    var e error
    if flags&2!=0 { // AUDCLNT_BUFFERFLAGS_SILENT
     for left:=n;left>0; {size:=left;if size>len(silence){size=len(silence)};_,e=os.Stdout.Write(silence[:size]);if e!=nil {break};left-=size}
    } else {
     if data==0 {return fmt.Errorf("null capture data")}
     _,e=os.Stdout.Write(unsafe.Slice((*byte)(unsafe.Pointer(data)),n))
    }
    if e!=nil {return e}
    got=true
   }
   v=invoke(capture,4,uintptr(frames))
   if err:=hrCheck(v,"ReleaseBuffer");err!=nil{return err}
   v=invoke(capture,5,uintptr(unsafe.Pointer(&available)))
   if err:=hrCheck(v,"GetNextPacketSize");err!=nil{return err}
  }
  if got {lastData=time.Now()} else if time.Since(lastData)>=30*time.Millisecond {if _,e:=os.Stdout.Write(silence);e!=nil{return e};lastData=time.Now()}
 }
}
func main(){
 if len(os.Args)==2 && os.Args[1]=="--self-test" {
  if err:=activateAsync.Find();err!=nil {fmt.Fprintln(os.Stderr,"WASAPI unavailable:",err);os.Exit(1)}
  fmt.Println("OK: Windows WASAPI process-loopback API found; stream still requires a game test")
  return
 }
 if len(os.Args)!=2 {fmt.Fprintln(os.Stderr,"Usage: process_loopback.exe <PID> | --self-test");os.Exit(2)}
 pid,e:=strconv.ParseUint(os.Args[1],10,32);if e!=nil || pid==0 {fmt.Fprintln(os.Stderr,"Invalid PID");os.Exit(2)}
 if e=run(uint32(pid));e!=nil{fmt.Fprintln(os.Stderr,"process_loopback:",e);os.Exit(1)}
}
