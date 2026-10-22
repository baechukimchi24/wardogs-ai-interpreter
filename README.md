# 🎮 WARDOGS AI Interpreter v1.0 Beta

### WARDOGS 실시간 영어 음성 인식 및 한국어 자막 번역 프로그램

**WARDOGS AI Interpreter**는 영어 음성 채팅을 이해하기 어려운 한국어 사용자를 위해 제작한 비공식 게임 통역 프로그램입니다.

게임에서 출력되는 오디오를 Windows에서 직접 수집하고, AI 음성 인식과 번역 모델을 이용해 영어 대화를 한국어 자막으로 표시합니다.

게임 화면 위에 자막을 표시하거나 별도 모니터에서 번역 내용을 확인할 수 있습니다.

**v1.0 Beta부터는 Python이나 Visual Studio 설치 없이 EXE 파일을 더블클릭하여 실행할 수 있습니다.**

## 📥 최신 버전 다운로드

👉 **[WARDOGS AI Interpreter v1.1 Beta 다운로드 (무설치 EXE)](https://github.com/baechukimchi24/wardogs-ai-interpreter/releases/tag/v1.1-beta)**

Windows 11 64비트용 무설치 버전입니다.

압축 해제 후 바로 실행할 수 있으며, 별도의 Python 개발 환경이나 Visual Studio 설치가 필요하지 않습니다.

---

## ✨ 주요 기능

- 🎙️ **실시간 영어 음성 인식:** WARDOGS 게임 오디오에서 영어 음성을 인식
- 🇰🇷 **한국어 자동 번역:** 로컬 AI 모델을 이용한 한국어 자막 출력
- 🖥️ **게임 자막 오버레이:** 게임 화면 위에 한국어 자막 표시
- ⌨️ **자막 단축키:** F10 등 사용자 지정 단축키로 ON/OFF
- 🤖 **로컬 AI 번역:** Qwen3.5, EXAONE, Argos, OPUS-MT 지원
- ⚡ **자막 우선 처리:** 연속 대사 발생 시 빠른 번역을 우선하도록 설정 가능
- 💬 **영어 답변 추천:** 상황에 맞는 영어 응답을 선택적으로 표시
- 🔊 **영어 TTS 출력:** 추천 문장을 원하는 Windows 출력 장치로 재생
- 🎧 **가상 오디오 장치 지원:** Virtual Audio Cable 및 다양한 오디오 장치 선택
- 🔈 **한국어 TTS:** 한국어 음성 통역 ON/OFF 지원
- 🎚️ **음성 감지 설정:** 최소 음성 길이와 종료 대기시간 직접 조절

---

## 💻 시스템 요구사항

**권장 환경**

- Windows 11 64비트
- NVIDIA RTX 그래픽카드 권장
- RAM 16GB 이상 권장
- 최초 AI 모델 다운로드를 위한 인터넷 연결

**개발 및 테스트 환경**

| 항목 | 사양 |
|---|---|
| 운영체제 | Windows 11 |
| CPU | Intel Core i7-14700K |
| GPU | NVIDIA RTX 5070 Ti 16GB |
| RAM | DDR5 32GB |

다른 PC에서도 사용할 수 있지만, 모든 하드웨어 환경에서 정상 작동을 보장하지 않습니다.

---

## 🚀 설치 및 실행 방법

### 1. 다운로드

위의 **최신 버전 다운로드** 링크를 클릭합니다.

GitHub Releases의 `Assets`에서 Windows Portable ZIP 파일을 다운로드합니다.

### 2. 압축 해제

다운로드한 ZIP을 원하는 폴더에 압축 해제합니다.

**중요:** EXE 파일만 따로 이동하지 마세요. 함께 제공된 `_internal` 등의 라이브러리 폴더도 유지해야 합니다.

### 3. 프로그램 실행

`WARDOGS Interpreter.exe`를 더블클릭합니다.

### 4. 번역 모델 다운로드

프로그램에서 `Local GGUF (offline)`을 선택한 후 사용할 AI 번역 모델을 다운로드합니다.

처음에는 **Qwen3.5 2B**를 추천합니다.

모델과 실행 엔진을 준비한 다음 `선택 모델 적용 및 번역 검증`을 클릭합니다.

### 5. 게임 연결

WARDOGS를 실행합니다.

프로그램에서 게임 프로세스가 인식되었는지 확인하고 `번역 시작`을 클릭하면 됩니다.

---

## 🤖 지원 번역 모델

| 모델 | 특징 |
|---|---|
| Qwen3.5 0.8B | 속도 우선 경량 모델 |
| Qwen3.5 2B | 속도와 번역 품질 균형 |
| Qwen3.5 4B | 번역 품질 우선 |
| EXAONE 3.5 2.4B | 한국어 번역 비교용 |
| Argos Translate | 빠른 오프라인 번역 |
| OPUS-MT | 영어→한국어 번역 특화 모델 |

모델은 선택적으로 다운로드하며, 일부 모델은 별도 라이선스 조건이 적용됩니다.

---

## ⚙️ 추천 초기 설정

| 설정 | 추천값 |
|---|---|
| Whisper | base.en 또는 small.en |
| 번역 방식 | Local GGUF (offline) |
| 번역 모델 | Qwen3.5 2B |
| 음성 감지 민감도 | 1~2 |
| 최소 음성 길이 | 150~200ms |
| 음성 종료 대기 | 240~300ms |
| 한국어 TTS | OFF |
| 영어 답변 추천 | OFF |
| 연속 발화 Argos 보조 번역 | ON |
| 자막 오버레이 단축키 | F10 |

게임 FPS와 번역 속도는 AI 모델 크기 및 GPU 사용 설정에 따라 달라질 수 있습니다.

---

## 🔊 영어 TTS 및 오디오 출력

영어 답변 추천 기능을 활성화하면 상황에 맞는 영어 문장이 표시됩니다.

원하는 답변 버튼을 클릭하면 선택한 Windows 오디오 출력 장치로 영어 음성이 재생됩니다.

Virtual Audio Cable 등을 이용하면 사용자의 오디오 라우팅 구성에 따라 게임 음성 채팅으로 전달할 수 있습니다.

게임 오디오는 Windows 프로세스별 오디오 캡처를 통해 수집하도록 설계되어 있으므로 가상 오디오 케이블을 게임 소리 입력용으로 설정할 필요는 없습니다.

---

## 📖 프로그램 사용 설명서

아래 이미지를 순서대로 참고해 주세요.

**1. 초기 설정 및 AI 모델 다운로드**

<img width="1448" height="1086" alt="menual_1" src="https://github.com/user-attachments/assets/b2fb6c34-70f2-4be7-864f-05e7525d3b80" />
**2. 음성 인식과 자막 최적화**

<img width="1448" height="1086" alt="menual_2" src="https://github.com/user-attachments/assets/78d39c40-fbae-4277-9003-8fb803b9bfdb" />
**3. 게임 연결 및 실제 사용 방법**

<img width="1448" height="1086" alt="menual_3" src="https://github.com/user-attachments/assets/bfb4951f-8ad3-4aa2-aa7a-95aaeaf50e41" />

**4. 실제 화면**

<img width="1919" height="1079" alt="menual_4" src="https://github.com/user-attachments/assets/710dceee-dab0-42a2-8179-cbddb461b0b6" />



---

## ⚠️ 주의사항

이 프로그램은 개인이 제작한 **비공식 커뮤니티 도구**이며 WARDOGS 개발사 및 운영사와 공식적인 관계가 없습니다.

- 게임 안티치트 호환성이 공식적으로 보장되지 않습니다.
- AI 음성 인식 및 번역이 항상 정확한 것은 아닙니다.
- GPU 및 CPU 사용량에 따라 게임 FPS가 달라질 수 있습니다.
- 온라인 번역 기능을 사용할 경우 영어 인식 텍스트가 외부 서비스로 전송될 수 있습니다.
- 일부 AI 모델은 비상업적 사용 및 재배포 관련 제한이 있습니다.
- Windows 보안 기능에서 다운로드한 EXE에 대해 경고가 표시될 수 있습니다.

현재 버전은 **Beta**이며, 사용자 환경에 따라 오류가 발생할 수 있습니다.

---

## 🛠️ 오류 제보 및 기능 요청

프로그램에서 오류가 발생하거나 개선하고 싶은 기능이 있다면 GitHub Issues에 남겨주세요.

👉 **[오류 제보 및 개선 요청](https://github.com/baechukimchi24/wardogs-ai-interpreter/issues)**

가능하다면 Windows 버전, CPU/GPU 사양, AI 모델, 오류 로그를 함께 작성해 주세요.

API 키, 개인정보 등 민감한 정보는 첨부하지 마세요.

---

## 📌 프로젝트 정보

- 프로그램: WARDOGS AI Interpreter
- 버전: v1.0 Beta
- 운영체제: Windows 11 x64
- 실행 방식: 무설치 Portable EXE
- 번역: 로컬 AI / 선택형 온라인 번역
- 개발 상태: 공개 베타 테스트

**영어를 몰라도 WARDOGS에서 다른 플레이어와 소통할 수 있도록 돕는 것이 이 프로젝트의 목표입니다.**
