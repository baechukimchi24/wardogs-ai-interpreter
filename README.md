🎮 WARDOGS AI Interpreter v0.9

WARDOGS 실시간 영어 음성 인식 및 한국어 자막 번역 프로그램

WARDOGS AI Interpreter는 영어 음성 채팅을 이해하기 어려운 한국어 사용자를 위해 제작한 비공식 게임 통역 프로그램입니다.

WARDOGS 게임에서 출력되는 오디오를 Windows에서 직접 수집하고, AI 음성 인식 및 번역 모델을 이용해 영어 대화를 한국어 자막으로 표시합니다.

게임 화면 위에 자막을 표시하거나 별도 모니터에서 번역 내용을 확인할 수 있습니다.

무료 로컬 AI 모델을 지원하므로 OpenAI API 키나 유료 구독 없이도 사용할 수 있습니다.

<img width="1448" height="1086" alt="menual_1" src="https://github.com/user-attachments/assets/b2fb6c34-70f2-4be7-864f-05e7525d3b80" />
<img width="1448" height="1086" alt="menual_2" src="https://github.com/user-attachments/assets/78d39c40-fbae-4277-9003-8fb803b9bfdb" />
<img width="1448" height="1086" alt="menual_3" src="https://github.com/user-attachments/assets/bfb4951f-8ad3-4aa2-aa7a-95aaeaf50e41" />
<img width="1919" height="1079" alt="menual_4" src="https://github.com/user-attachments/assets/710dceee-dab0-42a2-8179-cbddb461b0b6" />

✨ 주요 기능

🎙️ 실시간 영어 음성 인식: WARDOGS 프로세스의 게임 오디오를 직접 캡처해 영어 음성을 텍스트로 변환

🇰🇷 한국어 자동 번역: 인식한 영어 대사를 AI 모델로 번역해 자막으로 표시

🖥️ 게임 자막 오버레이: 게임 화면 위에 한국어 자막 표시

⌨️ 자막 단축키: F10 등 사용자 지정 단축키로 자막 ON/OFF

🤖 다양한 로컬 AI 모델: Qwen3.5, EXAONE, Argos 및 OPUS-MT 번역 지원

⚡ 자막 우선 처리: 연속 대화가 밀리면 Argos 번역으로 우회하는 기능 제공

💬 영어 답변 추천: 상황에 맞는 영어 응답을 선택적으로 표시

🔊 영어 TTS 송출: 추천 영어 답변을 선택한 오디오 출력 장치로 재생

🎧 가상 오디오 장치 지원: Virtual Audio Cable, 오디오 인터페이스 등 Windows 출력 장치 선택 가능

🔈 한국어 음성 통역: 한국어 TTS 기능 ON/OFF 지원

🎚️ 음성 감지 설정: 최소 음성 길이와 음성 종료 대기시간 직접 조절

게임 메모리 수정이나 DLL 주입 없이 Windows 오디오 캡처 기능을 이용하도록 설계되었습니다.

💻 시스템 요구사항

지원 환경

Windows 11 64비트

NVIDIA GPU 권장

RAM 16GB 이상 권장

최초 설치 및 AI 모델 다운로드를 위한 인터넷 연결

개발 및 테스트 환경

CPU: Intel Core i7-14700K

GPU: NVIDIA GeForce RTX 5070 Ti 16GB

RAM: DDR5 32GB

OS: Windows 11

다른 CPU나 GPU에서도 사용할 수 있으나, 모든 환경에서 동작을 보장하지 않습니다.

AI 모델의 크기와 실행 방식에 따라 게임 FPS 및 번역 지연시간이 달라질 수 있습니다.

📥 다운로드 및 설치

최신 설치 파일은 GitHub Releases에서 다운로드할 수 있습니다.

👉 **[최신 버전 다운로드](https://github.com/baechukimchi24/wardogs-ai-interpreter/releases/latest)**

설치 방법

Releases에서 설치 ZIP 파일을 다운로드합니다.

원하는 폴더에 압축을 해제합니다.

INSTALL_AND_START.bat을 실행합니다.

최초 실행 시 Python 및 필수 라이브러리가 자동으로 설치됩니다.

프로그램이 실행되면 번역 방식을 선택합니다.

사용할 AI 번역 모델과 실행 엔진을 다운로드합니다.

선택 모델 적용 및 번역 검증을 눌러 정상 작동 여부를 확인합니다.

WARDOGS를 실행한 후 프로그램에서 번역 시작을 누릅니다.

Visual Studio나 Ollama를 별도로 설치할 필요가 없도록 구성했습니다.

단, Windows 보안 설정이나 드라이버 환경에 따라 추가 설정이 필요할 수 있습니다.

🤖 지원 번역 모델

모델

특징

Qwen3.5 0.8B

가벼운 실시간 번역 실험용

Qwen3.5 2B

속도와 번역 품질의 균형

Qwen3.5 4B

높은 번역 품질 우선

EXAONE 3.5 2.4B

한국어 번역 비교용

Argos Translate

빠르고 가벼운 오프라인 번역

OPUS-MT

영어→한국어 번역 특화 모델

번역 모델은 프로그램 내부에서 선택적으로 다운로드할 수 있습니다.

처음 사용하는 경우 Qwen3.5 2B 또는 Argos Translate를 추천합니다.

일부 모델은 별도의 라이선스 및 사용 조건이 적용됩니다. 특히 EXAONE 모델은 비상업적·연구 목적 등 라이선스 조건을 확인해야 합니다.

⚙️ 추천 초기 설정

설정

권장값

Whisper 음성 인식

base.en 또는 small.en

번역 방식

Local GGUF (offline)

번역 모델

Qwen3.5 2B

음성 감지 민감도

1~2

최소 음성 길이

150~200ms

음성 종료 대기

240~300ms

한국어 TTS

OFF

영어 답변 추천

OFF

연속 발화 Argos 보조 번역

ON

자막 오버레이 단축키

F10

게임 프레임을 우선한다면 가벼운 번역 모델과 적은 GPU 레이어 수부터 시험하는 것이 좋습니다.

🔊 영어 TTS 및 오디오 출력

영어 답변 추천 기능을 켜면 상황에 맞는 영어 문장이 표시됩니다.

사용자가 원하는 답변 버튼을 클릭하면 선택한 Windows 오디오 출력 장치로 영어 TTS가 재생됩니다.

Virtual Audio Cable 등의 가상 오디오 장치를 이용하면 별도의 오디오 라우팅 구성을 통해 게임 음성 채팅으로 전달할 수 있습니다.

게임 오디오 입력은 가상 케이블이 아니라 Windows 프로세스별 오디오 캡처를 사용하도록 설계되어 있습니다.

기존 마이크나 오디오 인터페이스 라우팅을 프로그램에서 자동으로 변경하지 않습니다.

📖 프로그램 사용 설명서

아래 이미지를 순서대로 참고해 주세요.

1. 초기 설정 및 번역 모델 다운로드

2. 음성 인식 및 자막 최적화 설정

3. 실제 게임 연결 및 사용 방법

⚠️ 주의사항

이 프로그램은 개인이 제작한 비공식 커뮤니티 도구이며 WARDOGS 개발사 및 운영사와 공식적인 관계가 없습니다.

게임 안티치트와의 호환성이 공식적으로 보장되지 않습니다.

사용 중 오류나 충돌이 발생하면 프로그램을 중지하세요.

음성 인식 및 AI 번역 결과가 항상 정확한 것은 아닙니다.

온라인 번역 기능 사용 시 음성 인식 텍스트가 외부 서비스로 전송될 수 있습니다.

게임 중 GPU 및 CPU 사용량이 증가할 수 있습니다.

일부 AI 모델의 상업적 사용 및 재배포에는 별도 제한이 적용됩니다.

프로그램은 베타 버전이며 개발 및 테스트 과정에서 예기치 않은 오류가 발생할 수 있습니다.

🛠️ 오류 제보 및 개선 요청

프로그램 실행 중 문제가 발생하거나 개선하고 싶은 기능이 있다면 GitHub Issues에 남겨주세요.

👉 오류 제보 및 기능 요청

가능하다면 Windows 버전, CPU/GPU 사양, 사용 중인 AI 모델, 오류 메시지 등을 함께 알려주세요.

비밀번호, API 키, 개인 음성 기록 등 민감한 정보는 첨부하지 마세요.

📌 프로젝트 정보

프로그램: WARDOGS AI Interpreter

버전: v0.9 Beta

지원 운영체제: Windows 11 x64

번역 방식: 로컬 AI 및 선택적 온라인 번역

배포 형태: ZIP 기반 자동 설치

개발 상태: 베타 테스트

영어를 몰라도 WARDOGS에서 다른 플레이어와 소통할 수 있도록 만드는 것이 이 프로젝트의 목표입니다.
