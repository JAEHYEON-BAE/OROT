# OROT 도메인 연결·Mac mini 호스팅·AWS 이전 가이드

작성·코드 대조: **2026-09-12**. 대상 저장소: `/Users/jaehyeon/PersonalProjects/OROT`.

이 문서는 **도메인을 구입 → Mac mini에서 해당 도메인으로 운영 → 같은 주소를 유지하며 AWS Lightsail로 이전**하는 한 가지 완결된 절차를 설명한다. 명령을 실행할 위치, 생성할 파일, 성공 기준과 복구 절차를 포함한다.

**이 문서 작성만으로 도메인 구매, Cloudflare 설정, AWS 생성, 현재 서비스 변경이 실행되지는 않는다.** 아래의 설정 파일과 스크립트는 해당 단계에서 직접 생성한다. 기존에 수정 중인 코드는 덮어쓰지 않는다.

## 목차

1. [선택한 구성과 비용](#step-1)
2. [준비물·변수·현재 상태](#step-2)
3. [도메인 구입과 Cloudflare DNS](#step-3)
4. [Mac의 운영용 Docker 설정](#step-4)
5. [Cloudflare Tunnel과 HTTPS 연결](#step-5)
6. [서비스 주소 변경과 실제 검증](#step-6)
7. [관리자 페이지 접속](#step-7)
8. [Mac 자동 시작·절전·정전](#step-8)
9. [DB·설정의 암호화 백업과 복구 연습](#step-9)
10. [운영·배포·장애 확인](#step-10)
11. [AWS 계정·Lightsail 서버 준비](#step-11)
12. [AWS에 소스·설정·이미지 준비](#step-12)
13. [사전 DB 복원과 비공개 검증](#step-13)
14. [최종 이전: Mac 중지 → AWS 활성화](#step-14)
15. [AWS 자동 시작·외부 백업](#step-15)
16. [이전 실패 시 복구](#step-16)
17. [증상별 해결표](#step-17)
18. [완료 체크리스트와 참고 자료](#step-18)

<a id="step-1"></a>

## 1. 선택한 구성과 비용

### 1.1 공개 주소는 처음부터 하나로 고정한다

예시 최종 주소는 `https://orot.example.com`이다. `example.com`은 설명용 도메인이므로 실제로 구입한 도메인으로 바꾼다. `orot` 대신 `app`을 사용해도 되지만 운영을 시작한 뒤에는 호스트 이름을 자주 바꾸지 않는다.

```text
1단계
사용자 → https://orot.example.com → Cloudflare → Tunnel → Mac mini
                                                        ├─ web
                                                        ├─ api
                                                        ├─ collector
                                                        └─ postgres + 영구 볼륨

2단계
사용자 → https://orot.example.com → Cloudflare → 같은 Tunnel → AWS Lightsail
                                                            └─ 같은 Docker 서비스
Mac mini는 개발용으로 전환
```

도메인 등록기관은 주소의 소유권과 갱신을 관리한다. Cloudflare DNS는 주소를 연결하고, Cloudflare Tunnel은 서버에서 시작하는 외부 연결로 웹 트래픽을 전달한다. **실제 프로그램과 DB는 1단계에서는 Mac, 2단계에서는 AWS에서 실행된다.**

현재의 Tailscale Funnel은 `*.ts.net` 범위의 도메인만 지원한다. 구매한 주소를 기존 Funnel 주소에 CNAME으로 연결하는 것만으로는 사용자 도메인의 HTTPS 호스팅이 완성되지 않는다. 이 가이드에서는 공개 접속을 Cloudflare Tunnel로 바꾼다. 사설 관리 접속에 쓰는 Tailscale은 계속 사용할 수 있다. [Tailscale Funnel의 제한](https://tailscale.com/docs/features/tailscale-funnel)

Cloudflare Tunnel은 서버에서 외부로 연결하므로 공유기의 웹 포트 포워딩이나 Mac의 공인 고정 IP가 필요하지 않다. AWS로 옮긴 뒤에도 Tunnel을 유지하며, 이 가이드의 AWS 서버에는 웹용 80/443 인바운드 포트를 열지 않는다. [Cloudflare Tunnel 개요](https://developers.cloudflare.com/tunnel/)

### 1.2 예상 비용과 책임

| 항목 | Mac 단계 | AWS 단계 |
|---|---|---|
| 도메인 | 연간 등록·갱신 비용 | 같은 도메인 계속 사용 |
| Cloudflare | 기본 DNS·Tunnel 구성을 우선 사용; 가입 화면의 선택 요금제 확인 | 동일 |
| 서버 | Mac 전력·인터넷·장비 유지 | Lightsail 인스턴스 요금 |
| 백업 | iCloud 또는 외장 저장소 | S3 등 별도 저장소 요금 |
| 운영 | 절전·로그인·정전·백업 관리 | OS·Docker·백업·장애 관리 |

Lightsail Linux/Public IPv4 일반 번들은 현재 2GB 월 \$12, 4GB \$24, 8GB \$44다. 초기 후보는 **4GB**이며 웹 빌드와 DB를 함께 운영하면서 부족하면 늘린다. 이것은 부하 테스트로 보장한 용량이 아니다. 도메인·세금·스냅샷·추가 트래픽·S3는 별도다. 서버 생성 시 리전과 최종 금액을 다시 확인한다. **Lightsail은 중지만 해도 요금이 계속 발생한다.** [요금](https://aws.amazon.com/lightsail/pricing/), [과금 안내](https://aws.amazon.com/lightsail/faq/)

서버 한 대는 단일 장애 지점이다. 이 가이드는 백업을 통한 복구를 마련하지만 무중단·다중 리전 운영을 보장하지 않는다.

<a id="step-2"></a>

## 2. 준비물·변수·현재 상태

### 2.1 준비물

- 현재 OROT이 실행되는 Mac mini와 macOS 관리자 권한.
- 도메인 등록기관 계정, Cloudflare 계정. 복구 이메일과 MFA를 설정한다.
- AWS 이전 때: AWS 계정, 결제 수단, MFA, Lightsail SSH 키.
- 비밀번호 관리자: 관리자 키, VAPID 키, Tunnel 토큰, 백업 복구 키 보관.
- 기존 `.env`와 DB. **기존 `.env`를 `.env.example`로 덮어쓰지 않는다.**

아래는 현재 저장소의 기본값을 전제로 한다. 별도 변경했다면 실제 값에 맞춰 명령의 포트를 조정한다.

| 구분 | 값 |
|---|---|
| Mac 프로젝트 | `/Users/jaehyeon/PersonalProjects/OROT` |
| AWS 프로젝트 | `/home/ubuntu/OROT` |
| Compose 프로젝트 | `orot` |
| DB 역할 / DB 이름 | `orot` / `orot` |
| 운영 DB 볼륨 | `orot_postgres_data` |
| Mac·AWS 내부 웹 / API / DB 포트 | 3000 / 8000 / 5432 |
| 서버 내부 API 주소 | `http://api:8000` |
| 공개할 서비스 | `web:3000`만 |

### 2.2 터미널 변수와 명령 약속

**[Mac · 프로젝트 루트]** 새 터미널마다 실행한다. `orot.example.com`만 먼저 실제 주소로 바꾼다.

```bash
cd /Users/jaehyeon/PersonalProjects/OROT
export OROT_HOST=orot.example.com
```

`OROT_HOST`는 주소를 담는 공개 값이다. 비밀 값을 셸 명령에 붙여 넣거나 `.env`를 `source`하지 않는다. 현재 `.env`에는 공백이 있는 백업 경로도 있어 셸 스크립트로 실행하기에 적합하지 않다.

§4에서 `compose.hosted.yaml`을 만든 다음에는 아래 함수를 Mac과 AWS 양쪽에서 사용한다.

```bash
set -o pipefail
dc() {
  docker compose -f compose.yaml -f compose.prod.yaml -f compose.hosted.yaml "$@"
}
```

`pipefail`은 파이프라인 앞부분이 실패해도 실패로 처리하게 한다. 각 단계에서 오류가 나면 원인을 해결하기 전에는 다음 명령으로 넘어가지 않는다.

함수는 현재 터미널에만 존재한다. `dc: command not found`가 나오면 프로젝트 루트로 이동하고 다시 정의한다. 이후의 `dc`는 항상 위 세 파일을 순서대로 적용한다.

파일 생성 방법: Mac에서는 편집기로 지정한 경로에 새 파일을 만들고 코드 블록의 **내용만** 저장한다. 터미널에서는 `nano compose.hosted.yaml`처럼 열고 붙여 넣은 뒤 `Ctrl+O`, Enter로 저장하고 `Ctrl+X`로 종료할 수 있다. AWS의 `/etc/systemd/system/` 파일은 `sudo nano /etc/systemd/system/orot.service`처럼 관리자 권한으로 편집한다. 이미 파일이 있으면 먼저 백업하고 차이를 확인한다. 코드 블록의 앞뒤 세 개 백틱은 파일에 넣지 않는다.

### 2.3 현재 서비스와 복구 자료 확보

**[Mac · 프로젝트 루트]**

```bash
git status --short
docker context show
colima status
docker compose version
docker compose ps
curl -fsS http://127.0.0.1:8000/healthz
make backup
make backup-env
mkdir -p backups/domain-transition
chmod 700 backups/domain-transition
cp -p .env backups/domain-transition/before-domain.env
chmod 600 backups/domain-transition/before-domain.env
```

성공 기준: API 응답의 `status`와 `database`가 `ok`, DB 덤프 생성, `.env` 암호화 백업 성공. `make backup-env`가 실패하면 먼저 기존 키체인 설정을 복구한다. `make backup-env-setup`은 키체인 암호를 설정하는 명령이므로 **기존 암호를 모른 채 새 암호로 덮어쓰지 않는다.**

현재 Mac은 Colima를 사용하는 구성을 전제로 한다. Docker Desktop으로 바꿔서 실행하면 다른 Docker 엔진·볼륨을 보게 될 수 있다. 빈 DB가 보인다고 초기화하지 말고 Docker context를 확인한다.

`git status`에 보이는 기존 수정은 보존한다. 도메인 작업과 관계없는 파일을 되돌리거나 일괄 커밋하지 않는다.

<a id="step-3"></a>

## 3. 도메인 구입과 Cloudflare DNS

### 3.1 도메인 구입

1. 원하는 등록기관에서 도메인의 등록 가능 여부를 확인한다. 등록기관은 Cloudflare일 필요가 없다.
2. 첫해 할인뿐 아니라 **갱신 가격**, 이전 조건, 개인정보 보호 제공 여부를 확인한다.
3. 도메인을 등록하고 소유자 이메일 인증을 완료한다.
4. 자동 갱신과 결제 만료 알림을 켠다. 복구 이메일은 해당 도메인이 없어도 접근 가능한 주소를 사용한다.
5. 운영 주소를 `orot.<구입한 도메인>`으로 결정한다. 이후 단계에서는 이 주소만 사용한다.

이 가이드는 이미 존재하는 이메일·다른 웹사이트가 없는 새 도메인을 기준으로 한다. 기존 도메인을 쓰면 MX·TXT·기존 서비스 DNS 레코드를 먼저 내보내고 보존한다.

### 3.2 Cloudflare를 DNS 관리자로 지정

1. Cloudflare 대시보드에서 도메인 추가 메뉴를 연다. UI에 따라 `Add a domain` 또는 `Add a site`로 표시될 수 있다.
2. `example.com`처럼 **구입한 최상위 도메인**을 입력한다. `https://`나 `orot.`은 넣지 않는다.
3. 기본 DNS·Tunnel 사용에 필요한 요금제를 선택한다. 이 가이드에는 유료 Load Balancing이 필요하지 않다.
4. Cloudflare가 지정한 네임서버 두 개를 기록한다.
5. 등록기관의 네임서버 설정에서 기존 값을 Cloudflare 지정값으로 교체한다. 임의의 Cloudflare 네임서버를 사용하면 안 된다.
6. 다른 DNS 업체에서 DNSSEC를 켜둔 도메인은 기존 DS 레코드 처리 안내를 따른다. 오래된 DS 레코드를 남긴 채 업체를 바꾸면 이름 해석이 실패할 수 있다.
7. Cloudflare 상태가 `Active`가 될 때까지 기다린다. 이후 Cloudflare DNSSEC를 켜면 등록기관에 안내된 DS 값을 설정한다.

**[Mac]** 등록한 도메인으로 바꿔 확인한다.

```bash
dig NS example.com +short
```

성공 기준: Cloudflare가 배정한 네임서버가 반환되고 도메인이 `Active`. 기존 업체의 A 레코드나 Funnel CNAME을 `orot`에 미리 추가하지 않는다. §5에서 Tunnel 경로를 등록하며 연결한다. [Cloudflare 전체 DNS 설정](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/)

### 3.3 HTTPS와 캐시의 기본 원칙

- Cloudflare의 해당 도메인에서 Edge Certificate가 활성 상태인지 확인한다.
- 최종 접속은 항상 `https://`를 사용한다. 필요하면 도메인 전체에 HTTPS 리다이렉트를 설정한다.
- 이 가이드의 HTTP 구간은 같은 Docker 네트워크의 `cloudflared → web:3000`이다. 인터넷을 지나는 Tunnel 구간은 암호화된다. 이 구성에 맞추려고 SSL 설정을 `Flexible`로 바꿀 필요는 없다.
- 처음에는 별도의 `Cache Everything` 규칙을 만들지 않는다. 동적 HTML·구독 API·RSS·ICS에 강제 캐시를 적용하지 않는다.
- 공개 사이트 전체에 Cloudflare Access 로그인을 요구하면 RSS 리더와 캘린더 앱이 읽지 못할 수 있다. 관리자 화면은 별도 공개하지 않고 §7의 로컬/SSH 방식으로 접속한다.

<a id="step-4"></a>

## 4. Mac의 운영용 Docker 설정

### 4.1 운영용 오버레이 작성

현재 `compose.prod.yaml`은 웹만 production 이미지로 고정한다. API에는 개발용 `--reload`, API·collector에는 소스 마운트가 남아 있다. 아래 별도 파일로 이를 해제한다. 원래 개발 파일은 유지한다.

**[Mac · 프로젝트 루트]** `compose.hosted.yaml`을 아래 내용으로 만든다.

```yaml
name: orot

x-hosted-logging: &hosted-logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"

services:
  postgres:
    logging: *hosted-logging

  api:
    volumes: !reset []
    command:
      - uvicorn
      - orot_api.main:app
      - --host
      - "0.0.0.0"
      - --port
      - "8000"
    environment:
      WATCHFILES_FORCE_POLLING: "false"
    logging: *hosted-logging

  collector:
    volumes: !reset []
    logging: *hosted-logging

  web:
    logging: *hosted-logging

  cloudflared:
    image: ${CLOUDFLARED_IMAGE:?CLOUDFLARED_IMAGE must be set in .env}
    profiles: [public]
    restart: unless-stopped
    command: [tunnel, --no-autoupdate, run]
    env_file:
      - .env.tunnel
    depends_on:
      web:
        condition: service_started
    logging: *hosted-logging
```

`cloudflared`에는 공개 포트가 없다. 나머지 서비스의 `127.0.0.1` 바인딩도 그대로 유지한다. `localhost:3000`을 Tunnel의 대상 주소로 쓰지 않는다. 컨테이너 안의 localhost는 Mac이나 웹 컨테이너가 아니다.

`public` 프로필은 AWS 준비 단계에서 Tunnel을 실수로 시작하는 일을 줄인다. 평소 `dc up -d`만 실행하면 새 Tunnel은 시작되지 않는다. 공개 실행은 `dc --profile public up -d`, Tunnel만 시작할 때는 `dc up -d cloudflared`를 사용한다.

Compose가 `!reset`을 인식하지 못하면 최신 Compose 플러그인으로 갱신한다. `docker-compose` 구버전 대신 `docker compose`를 사용한다.

### 4.2 cloudflared 이미지 버전 고정

**[Mac · 프로젝트 루트]**

```bash
docker pull cloudflare/cloudflared:latest
venv/bin/python - <<'PY'
import subprocess
from pathlib import Path
image = subprocess.check_output([
    'docker', 'image', 'inspect', 'cloudflare/cloudflared:latest',
    '--format', '{{index .RepoDigests 0}}'
], text=True).strip()
assert image.startswith('cloudflare/cloudflared@sha256:')
p = Path('.env')
lines = [line for line in p.read_text().splitlines()
         if not line.startswith('CLOUDFLARED_IMAGE=')]
p.write_text('\n'.join(lines + ['CLOUDFLARED_IMAGE=' + image]) + '\n')
p.chmod(0o600)
print('cloudflared image digest saved')
PY
```

`latest`를 한 번 받아 그 이미지의 digest를 `.env`에 저장한다. 이후 재기동 때 임의로 버전이 바뀌지 않는다. AWS가 다른 CPU 아키텍처이면 §12에서 그 서버에서 pull한 이미지로 값을 다시 확인한다.

### 4.3 새 비밀 파일의 제외 규칙

기존 `.gitignore`와 `.dockerignore`에는 `.env`와 `.env.*` 제외 규칙이 있다. 따라서 `.env.tunnel`도 커밋·이미지 빌드 대상에서 제외된다. 다음 파일은 운영자가 직접 작성하므로 비밀을 넣지 않는다.

- `compose.hosted.yaml`: 공개 가능한 구성.
- `infra/orot-hosted-start.sh`: §8에서 작성할 자동 시작 스크립트.
- `infra/orot-portable-backup.sh`: §9에서 작성할 백업 스크립트.

아래 두 줄을 **`.gitignore`와 `.dockerignore` 양쪽에** 추가한다. 백업 디렉토리는 이미 제외되어 있다.

```text
.orot-host-disabled
*.agekey
```

<a id="step-5"></a>

## 5. Cloudflare Tunnel과 HTTPS 연결

### 5.1 이름이 고정된 관리형 Tunnel 생성

1. Cloudflare 대시보드의 `Networking → Tunnels`를 연다. 계정 UI에 따라 Cloudflare One/Zero Trust의 `Networks → Connectors/Tunnels`에 있을 수 있다.
2. `cloudflared` 타입의 관리형 Tunnel을 만든다. 이름은 **`orot-public`**으로 한다.
3. connector 설치 환경으로 `Docker`를 선택한다.
4. 화면에 표시되는 실행 명령은 실행하지 말고, 그 안의 **Tunnel token 값만** 비밀번호 관리자에 저장한다.
5. 터널 ID와 이름을 운영 기록에 남긴다. Quick Tunnel의 임시 `trycloudflare.com` 주소를 사용하지 않는다.

이 토큰을 가진 장비는 해당 Tunnel의 connector가 될 수 있다. 채팅·문서·GitHub·터미널 명령 인수에 토큰을 붙여 넣지 않는다. [Tunnel 생성 절차](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/)

### 5.2 토큰을 표시 없이 저장

**[Mac · 프로젝트 루트]** 아래 명령을 실행하면 입력한 토큰은 화면에 표시되지 않는다.

```bash
venv/bin/python - <<'PY'
from getpass import getpass
from pathlib import Path
token = getpass('Cloudflare Tunnel token: ').strip()
if not token or any(c.isspace() for c in token):
    raise SystemExit('토큰 값만 입력하세요.')
p = Path('.env.tunnel')
p.touch(mode=0o600, exist_ok=True)
p.chmod(0o600)
p.write_text('TUNNEL_TOKEN=' + token + '\n')
print('Saved .env.tunnel')
PY
git check-ignore .env .env.tunnel
```

성공 기준: 마지막 명령이 두 파일을 모두 출력한다. `git ls-files .env .env.tunnel`은 아무것도 출력하지 않아야 한다. ignore 규칙은 이미 추적된 파일을 자동 제거하지 않으므로 결과가 있으면 공개 배포 전에 별도로 정리한다.

`TUNNEL_TOKEN`은 cloudflared의 공식 환경 변수다. Compose는 이 파일을 **cloudflared 컨테이너에만** 전달한다. Docker 관리 권한이 있는 사용자는 컨테이너 환경을 읽을 수 있으므로 Docker 접근 자체를 관리자 권한으로 취급한다. [실행 매개변수](https://developers.cloudflare.com/tunnel/reference/run-parameters/)

### 5.3 공개 주소의 대상 설정

Tunnel의 `Published application routes` 또는 `Public Hostnames`에서 다음 항목을 만든다.

| 항목 | 입력값 |
|---|---|
| Subdomain | `orot` |
| Domain | 구입한 `example.com` |
| Path | 비워둠 |
| Service type | HTTP |
| Service URL | `web:3000` |

- Origin Host Header를 `web` 또는 `localhost`로 덮어쓰지 않는다. 기본 공개 호스트 전달을 유지한다.
- `api:8000`, `postgres:5432`, 관리자 전용 hostname은 등록하지 않는다.
- 저장 시 해당 hostname의 DNS 레코드가 생성되었는지 확인한다. 기존 A/AAAA/CNAME이 같은 이름을 차지하면 그 용도를 먼저 확인한 뒤 충돌을 해소한다.
- AWS 이전 때도 이 **같은 Tunnel·같은 hostname·같은 내부 서비스 이름**을 유지한다.

<a id="step-6"></a>

## 6. 서비스 주소 변경과 실제 검증

### 6.1 현재 설정에서 공개 URL만 갱신

**[Mac · 프로젝트 루트]** §2의 `OROT_HOST`가 실제 주소인지 확인한 뒤 실행한다.

```bash
venv/bin/python - <<'PY'
import os
from pathlib import Path
host = os.environ['OROT_HOST'].strip()
if not host or '://' in host or '/' in host or host.endswith('example.com'):
    raise SystemExit('OROT_HOST를 실제 구입한 도메인의 호스트로 설정하세요.')
p = Path('.env')
updates = {'PUBLIC_WEB_URL': 'https://' + host, 'ENVIRONMENT': 'production'}
lines = p.read_text().splitlines()
for key, value in updates.items():
    lines = [line for line in lines if not line.startswith(key + '=')]
    lines.append(key + '=' + value)
p.write_text('\n'.join(lines) + '\n')
p.chmod(0o600)
PY
```

함께 확인할 값:

- `ADMIN_API_KEY`: 기존 운영 키 유지. 운영 검증을 통과하는 충분히 긴 키.
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`: 기존 키 유지.
- `VAPID_SUBJECT`: 실제 연락 가능한 `mailto:` 주소.
- `CRAWLER_USER_AGENT`: OROT 이름과 실제 연락처. 현재 없는 `/about` 페이지를 있는 것처럼 적지 않는다.
- `DATABASE_URL`, DB 비밀번호, `POSTGRES_VOLUME_NAME`: 현재 작동하는 값 유지.
- `POSTGRES_VOLUME_EXTERNAL=true`: 기존 `orot_postgres_data`를 계속 사용.
- `API_BASE_URL`: Compose 내부의 `http://api:8000` 유지. 공개 도메인으로 바꾸지 않는다.

### 6.2 검증 후 실행

**[Mac · 프로젝트 루트]** §2의 `dc` 함수를 먼저 정의한다.

```bash
docker volume inspect orot_postgres_data --format '{{.Name}}'
dc config --quiet
dc --profile public up -d --build --wait
dc ps
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS -o /dev/null -w 'local web: %{http_code}\n' http://127.0.0.1:3000/
dc logs --tail=50 cloudflared
```

`config --quiet`는 비밀을 출력하지 않고 설정만 검사한다. 일반 `docker compose config`와 원본 `docker inspect` 출력에는 비밀 환경 변수가 포함될 수 있으므로 공개 채팅에 붙여 넣지 않는다.

`up`은 기존 DB 볼륨을 유지하며 필요한 컨테이너를 재생성한다. API·collector도 이제 이미지에 든 소스로 실행되므로 이후 소스 변경은 빌드·재생성이 필요하다. `.env` 변경에도 `restart`만 사용하지 않는다.

성공 기준:

- API와 PostgreSQL healthy, 웹·collector·cloudflared 실행 중.
- Tunnel 대시보드에 활성 connector 표시.
- `Registered tunnel connection` 계열 로그 또는 정상 연결 상태.
- 아래 외부 검사 성공.

```bash
curl -fsS -o /dev/null -w 'public web: %{http_code}\n' "https://$OROT_HOST/"
curl -fsS -o /dev/null -w 'calendar: %{http_code}\n' "https://$OROT_HOST/calendar"
curl -fsS -o /dev/null -w 'subscribe: %{http_code}\n' "https://$OROT_HOST/subscribe"
curl -fsS -o /dev/null -w 'RSS: %{http_code}\n' "https://$OROT_HOST/v1/feed.rss"
curl -fsS -o /dev/null -w 'ICS: %{http_code}\n' "https://$OROT_HOST/v1/releases.ics"
curl -sS -o /dev/null -w 'admin must be 404: %{http_code}\n' "https://$OROT_HOST/admin"
```

정상 페이지는 200, 공개 `/admin`은 404가 기대값이다. 휴대폰 Wi-Fi를 끄고 셀룰러에서도 확인한다. 로컬 성공만으로 외부 공개 성공을 판단하지 않는다.

### 6.3 새 도메인에서 푸시·캘린더 확인

1. 새 도메인의 구독 페이지에서 알림을 켠다.
2. iPhone은 새 주소를 Safari에서 연 뒤 홈 화면에 추가하고, 추가된 앱에서 구독한다.
3. RSS 리더·캘린더 앱에도 새 주소를 등록한다.
4. 관리자에서 `OROT 도메인 연결 테스트`라는 초안을 만들고 저장한다.
5. 실제 전송을 해도 되는 시점에 공개한다. **이 동작은 활성 구독자 전체에 새 일정 알림을 보낼 수 있다.** 본인만 받는다고 가정하지 않는다.
6. 발매·예약 날짜는 비워 두어 후속 날짜 알림이 생기지 않게 한다.
7. 통상 다음 스케줄러 주기 이후 알림을 확인하고, 눌렀을 때 새 도메인의 해당 상세 페이지로 이동하는지 확인한다.
8. 확인 후 필요하면 테스트 일정을 공개 취소한다. 삭제 여부는 배송 기록 보존 필요성에 따라 결정한다.

서버에서 전송 결과만 확인할 때는 다음처럼 URL·키를 조회하지 않는 집계를 사용한다. 공개한 일정 ID를 `123` 대신 넣는다.

```bash
dc exec -T postgres psql -U orot -d orot -c \
  "SELECT nd.status, count(*) FROM notification_deliveries nd JOIN listing_events e ON e.id=nd.event_id WHERE e.release_id=123 GROUP BY nd.status;"
```

`SENT`는 푸시 서비스로 전송 성공을 기록한 것이며 기기 화면 표시까지 보장하는 값은 아니다. 실제 알림과 클릭 결과를 별도로 확인한다.

기존 Funnel 주소와 새 도메인은 서로 다른 출처다. 기존 구독이 새 도메인의 구독으로 자동 이전되지는 않는다. 원래 사이트에서 알림을 끄고 새 사이트에서 다시 켜도록 안내한다. **이후 Mac → AWS 이전에서는 이 새 도메인과 VAPID 키를 유지하므로 다시 도메인을 바꿀 필요가 없다.** [Push API와 서비스워커 등록](https://www.w3.org/TR/push-api/)

### 6.4 기존 Funnel 공개 종료

새 주소의 검증과 사용자 안내가 끝난 후에 실행한다.

```bash
tailscale funnel status
```

이 Mac의 Funnel 설정이 **OROT 웹 하나만**을 위한 것이라면:

```bash
tailscale funnel reset
```

다른 서비스도 공개 중이면 전체 reset을 하지 않고 해당 포트/경로만 제거한다. Tailscale 자체를 삭제할 필요는 없다. Funnel을 끈 뒤에도 새 도메인이 열리는지 확인한다. 이전 Funnel 주소는 더 이상 서비스 주소로 안내하지 않는다.

<a id="step-7"></a>

## 7. 관리자 페이지 접속

### 7.1 Mac에서 운영할 때

Mac mini에서 `http://127.0.0.1:8000/admin`을 연다. 로그인 키는 `.env`의 `ADMIN_API_KEY`다. 공개 주소 뒤에 `/admin`을 붙이지 않는다.

다른 본인 Mac에서 관리해야 한다면 Mac mini의 원격 로그인(SSH)을 본인 계정에만 허용하고 사설 LAN/Tailscale 주소로 SSH 터널을 연다. 공유기에 SSH 포트를 무조건 공개하지 않는다.

```bash
ssh -N -L 18000:127.0.0.1:8000 jaehyeon@MAC_MINI_PRIVATE_ADDRESS
```

그 터미널을 유지한 채 브라우저에서 `http://127.0.0.1:18000/admin`으로 접속한다. `MAC_MINI_PRIVATE_ADDRESS`는 실제 사설 IP 또는 Tailscale 이름으로 바꾼다. SSH 터널을 종료하려면 `Ctrl+C`를 누른다.

### 7.2 AWS로 이전한 뒤

§11의 SSH 변수 설정 후 **관리하는 Mac에서** 실행한다.

```bash
ssh -i "$OROT_SSH_KEY" -N -L 18000:127.0.0.1:8000 "ubuntu@$OROT_AWS_IP"
```

접속 주소는 역시 `http://127.0.0.1:18000/admin`이다. 이 localhost는 SSH를 통해 AWS의 관리자 포트로 연결된다. AWS 보안 규칙에 8000을 공개할 필요가 없다.

<a id="step-8"></a>

## 8. Mac 자동 시작·절전·정전

### 8.1 운영 전용 시작 스크립트

현재 `infra/orot-start.sh`는 기존 두 Compose 파일만 사용한다. 새 운영 파일을 빠뜨리지 않도록 별도 스크립트를 만든다.

**[Mac · 프로젝트 루트]** `infra/orot-hosted-start.sh`:

```bash
#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
OROT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$OROT_ROOT"
if [ -f .orot-host-disabled ]; then
  echo "OROT host disabled; no services started"
  exit 0
fi
if ! colima status >/dev/null 2>&1; then
  colima start
fi
docker compose -f compose.yaml -f compose.prod.yaml -f compose.hosted.yaml \
  --profile public up -d --no-build --wait
curl -fsS http://127.0.0.1:8000/healthz
```

```bash
chmod +x infra/orot-hosted-start.sh
bash -n infra/orot-hosted-start.sh
```

이 스크립트는 부팅 때 네트워크 빌드를 하지 않는다. §6에서 정상 빌드한 이미지를 사용한다.

### 8.2 기존 LaunchAgent를 새 스크립트에 연결

기존 `com.orot.stack`과 같은 역할의 에이전트를 추가로 만들지 않는다. **기존 파일을 백업하고 교체**한다.

```bash
cp -p "$HOME/Library/LaunchAgents/com.orot.stack.plist" \
  backups/domain-transition/com.orot.stack.before.plist
venv/bin/python - <<'PY'
from pathlib import Path
import plistlib
root = Path.cwd()
path = Path.home() / 'Library/LaunchAgents/com.orot.stack.plist'
config = {
    'Label': 'com.orot.stack',
    'ProgramArguments': ['/bin/bash', str(root / 'infra/orot-hosted-start.sh')],
    'WorkingDirectory': str(root),
    'RunAtLoad': True,
    'StandardOutPath': str(root / 'backups/hosted-start.log'),
    'StandardErrorPath': str(root / 'backups/hosted-start.error.log'),
}
path.write_bytes(plistlib.dumps(config))
PY
plutil -lint "$HOME/Library/LaunchAgents/com.orot.stack.plist"
```

이미 등록된 경우 먼저 해제한다. 첫 명령이 등록 상태를 표시할 때만 `bootout`을 실행한다.

```bash
launchctl print "gui/$(id -u)/com.orot.stack"
launchctl bootout "gui/$(id -u)/com.orot.stack"
launchctl enable "gui/$(id -u)/com.orot.stack"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.orot.stack.plist"
```

`RunAtLoad`이므로 bootstrap 시 스크립트가 실행된다. `dc ps`와 새 도메인을 확인한다. 실패하면 `backups/hosted-start.error.log`를 먼저 확인한다.

### 8.3 절전과 재부팅의 한계

- 시스템 설정에서 디스플레이가 꺼져도 자동 잠자기에 들어가지 않도록 설정한다. 화면 끄기와 시스템 잠자기는 다르다.
- 가능한 경우 정전 후 자동 재시작을 켠다. 유선 인터넷과 UPS가 있으면 가정 내 중단 위험을 줄일 수 있다.
- Colima와 위 LaunchAgent는 **사용자 로그인 세션**에 의존한다. 전원이 켜졌다고 로그인 전부터 서비스가 돌아온다고 가정하지 않는다.
- FileVault가 켜져 있으면 재부팅 후 잠금 해제가 필요할 수 있다. 이를 피하려고 보안 기능을 임의로 끄기보다 운영 중단 가능성을 인지하고 AWS 이전 시 해소한다.
- 정기 점검 시 실제 재부팅 → 로그인 → Colima → 컨테이너 → Tunnel → 외부 도메인 순서로 복구되는지 확인한다.

[Apple 잠자기 설정](https://support.apple.com/en-gb/guide/mac-help/mchle41a6ccd/mac)

<a id="step-9"></a>

## 9. DB·설정의 암호화 백업과 복구 연습

### 9.1 백업에 반드시 포함할 것

DB에는 푸시 endpoint와 기기 키가 있고, `.env`에는 VAPID 개인키·관리자 키·Slack 웹훅 등이 있다. `.env.tunnel`도 새 비밀이다. 기존 `make backup-env`는 `.env.tunnel`까지 자동으로 백업하지 않는다.

이 절에서는 **DB 덤프 + `.env` + `.env.tunnel` + 소스 revision**을 하나의 암호화 파일로 만든다. Mac과 Linux에서 같은 형식을 사용한다. 기존 백업은 성공을 확인하기 전까지 유지한다.

### 9.2 복구용 age 키 만들기

**[Mac]** Homebrew가 있는 현재 환경에서:

```bash
brew install age
cd /Users/jaehyeon/PersonalProjects/OROT
mkdir -p backups/recovery
chmod 700 backups/recovery
age-keygen -o backups/recovery/orot.agekey
chmod 600 backups/recovery/orot.agekey
age-keygen -y backups/recovery/orot.agekey
```

마지막 출력 `age1...`은 **공개 수신자 키**다. 자동 백업 스크립트에는 이 공개 값만 전달한다. `orot.agekey`는 암호를 푸는 **개인키**이므로 비밀번호 관리자의 보안 파일과 별도 안전한 저장소에 보관한다. 서버·백업 파일·개인키가 모두 같은 디스크에만 있으면 디스크 고장에 대비할 수 없다. 이 키와 비밀번호 관리자의 복구 수단을 먼저 안전하게 보관한 다음 아래 자동 백업을 설정한다.

기존 파일이 있으면 새 키를 덮어쓰지 않는다. 이전 백업을 복원하려면 그때 사용한 개인키가 필요하다. [age 공식 프로젝트](https://github.com/FiloSottile/age)

### 9.3 이식 가능한 백업 스크립트

**[프로젝트 루트]** `infra/orot-portable-backup.sh`:

```bash
#!/bin/bash
set -euo pipefail
umask 077
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
OROT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$OROT_ROOT"
DEST="${1:?Pass the encrypted-backup directory}"
RECIPIENT="${2:?Pass the public age recipient}"
mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"
TMP="$(mktemp -d)"
OUT=""
cleanup() {
  rm -rf "$TMP"
  if [ -n "$OUT" ] && [ -f "$OUT.partial" ]; then
    rm -f "$OUT.partial"
  fi
}
trap cleanup EXIT
DC=(docker compose -f compose.yaml -f compose.prod.yaml -f compose.hosted.yaml)
"${DC[@]}" exec -T postgres pg_dump -U orot -d orot \
  --format=custom --no-owner --no-acl > "$TMP/database.dump"
test -s "$TMP/database.dump"
cp .env "$TMP/.env"
cp .env.tunnel "$TMP/.env.tunnel"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git rev-parse HEAD > "$TMP/source-revision.txt"
  if [ -n "$(git status --porcelain --untracked-files=normal)" ]; then
    echo 'WARNING: worktree is dirty; archive matching source separately' >&2
  fi
else
  cp backups/migration/source-revision.txt "$TMP/source-revision.txt"
fi
OUT="$DEST/orot-$(date -u +%Y%m%dT%H%M%SZ)-$$.tar.age"
tar -C "$TMP" -cf - database.dump .env .env.tunnel source-revision.txt \
  | age -r "$RECIPIENT" -o "$OUT.partial"
test -s "$OUT.partial"
mv "$OUT.partial" "$OUT"
echo "Encrypted backup: $OUT"
```

실행 예시의 `age1REPLACE_WITH_YOUR_PUBLIC_RECIPIENT`는 §9.2의 공개 값으로 바꾼다.

```bash
chmod +x infra/orot-portable-backup.sh
bash -n infra/orot-portable-backup.sh
infra/orot-portable-backup.sh \
  "$HOME/Library/Mobile Documents/com~apple~CloudDocs/OROT/portable" \
  age1REPLACE_WITH_YOUR_PUBLIC_RECIPIENT
```

iCloud 동기화 완료를 다른 기기에서 확인한다. 아래 복원 시험이 성공해야 백업을 신뢰할 수 있다. 스크립트는 오래된 백업을 자동 삭제하지 않으므로 용량과 보관 기간을 직접 관리한다.

### 9.4 Mac에서 매일 실행

**[Mac · 프로젝트 루트]**

```bash
cp -p "$HOME/Library/LaunchAgents/com.orot.backup.plist" \
  backups/domain-transition/com.orot.backup.before.plist
```

`com.orot.backup.plist`를 `backups/domain-transition/`에 복사한 뒤 아래 템플릿으로 교체한다. 경로와 공개 키를 본인의 값으로 바꾼다. 토큰·개인키는 plist에 넣지 않는다.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.orot.backup</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string>
    <string>/Users/jaehyeon/PersonalProjects/OROT/infra/orot-portable-backup.sh</string>
    <string>/Users/jaehyeon/Library/Mobile Documents/com~apple~CloudDocs/OROT/portable</string>
    <string>age1REPLACE_WITH_YOUR_PUBLIC_RECIPIENT</string>
  </array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>3</integer>
    <key>Minute</key><integer>15</integer>
  </dict>
  <key>StandardOutPath</key><string>/Users/jaehyeon/PersonalProjects/OROT/backups/portable-backup.log</string>
  <key>StandardErrorPath</key><string>/Users/jaehyeon/PersonalProjects/OROT/backups/portable-backup.error.log</string>
</dict></plist>
```

수정한 파일을 `$HOME/Library/LaunchAgents/com.orot.backup.plist`에 저장한다. 등록 상태를 먼저 확인한다. 이미 등록되어 있을 때만 bootout을 실행한다.

```bash
plutil -lint "$HOME/Library/LaunchAgents/com.orot.backup.plist"
launchctl print "gui/$(id -u)/com.orot.backup"
launchctl bootout "gui/$(id -u)/com.orot.backup"
launchctl enable "gui/$(id -u)/com.orot.backup"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.orot.backup.plist"
launchctl kickstart "gui/$(id -u)/com.orot.backup"
```

다음 날 새 날짜의 암호화 파일이 실제로 생성되는지도 확인한다.

### 9.5 운영 DB와 분리하여 복호화·복원 시험

**[Mac · 프로젝트 루트]** `OROT_BACKUP_FILE`을 실제 암호화 백업 경로로 바꾼다.

```bash
export OROT_BACKUP_FILE='/absolute/path/to/orot-TIMESTAMP.tar.age'
umask 077
mkdir -p backups/restore-drill
chmod 700 backups/restore-drill
age -d -i backups/recovery/orot.agekey -o backups/restore-drill/archive.tar "$OROT_BACKUP_FILE"
tar -xf backups/restore-drill/archive.tar -C backups/restore-drill
chmod 600 backups/restore-drill/.env backups/restore-drill/.env.tunnel
```

운영 DB나 `.env`에 직접 덮어쓰지 않는다. 아래 DB는 외부 네트워크와 공개 포트가 없는 임시 DB다.

```bash
docker run -d --name orot-restore-drill --network none \
  --tmpfs /var/lib/postgresql/data \
  -e POSTGRES_USER=orot -e POSTGRES_DB=orot \
  -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine
```

최대 60초 정도 기다려 다음 준비 상태 검사가 성공한 뒤 복원한다. 초기화 중 임시 소켓을 피하려고 TCP 주소를 지정한다.

```bash
docker exec orot-restore-drill pg_isready -h 127.0.0.1 -U orot -d orot
docker exec -i orot-restore-drill pg_restore -U orot -d orot \
  --no-owner --no-acl --exit-on-error < backups/restore-drill/database.dump
docker exec orot-restore-drill psql -U orot -d orot -c \
  'SELECT count(*) FROM releases; SELECT count(*) FROM device_tokens; SELECT version_num FROM alembic_version;'
```

기대하는 데이터 건수와 마이그레이션 버전인지 확인한 뒤 임시 컨테이너만 삭제한다.

```bash
docker rm -f orot-restore-drill
rm -rf backups/restore-drill
```

여기의 `trust`는 네트워크를 차단한 임시 DB에만 사용한다. 운영 DB에는 사용하지 않는다. 복호화 파일에는 키가 포함되므로 권한을 제한하고 시험 후 정리한다.

<a id="step-10"></a>

## 10. 운영·배포·장애 확인

### 10.1 일상 점검

- 외부 회선에서 메인·구독 페이지가 열린다.
- API/Postgres는 healthy, collector/cloudflared는 실행 중이다.
- 정기 백업의 최신 시각과 외부 복사본을 확인한다.
- 디스크 용량과 Docker 로그 증가를 확인한다.
- 도메인 갱신과 Cloudflare 인증서 상태를 확인한다.

```bash
dc ps
dc logs --tail=80 collector
dc logs --tail=80 cloudflared
df -h
docker system df
```

로그에는 운영 정보가 포함된다. 공유하기 전에 키·토큰·구독 URL을 확인한다. `docker system prune --volumes`, `docker volume prune`, `down -v`를 용량 확보용으로 실행하지 않는다.

현재 collector는 앱 내부 장애를 Slack으로 알릴 수 있지만 Mac 자체가 멈추면 알림 처리도 멈춘다. 다른 기기나 외부 모니터링 서비스에서 HTTPS 응답을 감시한다. 메인 화면 감시만으로 collector 중단을 탐지할 수 없으므로 스케줄러 상태도 확인한다.

### 10.2 코드 업데이트

1. 운영 revision을 정하고 `make lint`, `make test`, 웹 lint/test/build 또는 GitHub CI를 통과시킨다.
2. §9의 백업을 실행한다.
3. 앱 변경과 DB 스키마 변경 여부를 확인한다.
4. 마이그레이션이 없는 일반 업데이트는 `dc --profile public up -d --build --wait`로 적용한다.
5. 마이그레이션이 있으면 먼저 이미지를 빌드한다. 점검 시간에 cloudflared·web·collector·api를 중지하고 `dc run --rm --no-deps api alembic upgrade head`를 실행한 다음 시작한다.
6. 변경 화면·DB 연결·구독·백업을 검증한다.

`make prod`와 기존 시작 스크립트에는 `compose.hosted.yaml`이 포함되지 않는다. 공개 운영 이후에는 이 문서의 `dc` 또는 새 자동 시작 스크립트를 사용한다. 컨테이너 내부 파일을 직접 편집해 배포 코드를 변경하지 않는다.

<a id="step-11"></a>

## 11. AWS 계정·Lightsail 서버 준비

Mac의 도메인 운영을 확인한 뒤 이 절을 진행한다. **AWS 준비 중에도 운영 서버는 Mac이다.** AWS collector와 cloudflared는 §14까지 시작하지 않는다.

### 11.1 AWS 계정과 비용 알림

1. AWS 계정을 만들고 루트 사용자에 MFA를 설정한다.
2. 일상 작업용 관리 접근을 설정한다. 루트 사용자의 액세스 키는 만들지 않는다.
3. Billing에서 비용 알림을 설정한다. 예를 들어 US$30/50 기준은 알림이며 과금을 강제로 중단하는 장치가 아니다.
4. Lightsail에서 사용자와 가까운 리전을 선택한다. 한국 중심이라면 서울을 우선 검토한다.
5. Linux/Unix, OS Only, **Ubuntu 24.04 LTS, 4GB, Public IPv4**를 후보로 선택한다. OS·가격·리전 제공 여부는 생성 화면에서 확인한다.
6. 인스턴스 이름은 `orot-prod`로 한다. 운영 이후에도 OS 업데이트를 직접 관리한다.

### 11.2 고정 IP와 SSH

1. Lightsail Networking에서 같은 리전의 고정 IPv4를 만들고 인스턴스에 연결한다.
2. 이 IP는 관리용 SSH 접속 주소를 고정하기 위한 것이다. 공개 도메인 DNS는 Cloudflare Tunnel을 유지하며 AWS IP로 바꾸지 않는다.
3. 해당 리전·인스턴스의 SSH 개인키를 내려받아 Mac의 `~/.ssh/orot-lightsail.pem`에 보관한다.
4. Lightsail 방화벽의 SSH 22/TCP는 본인의 접속 IP로 제한한다. 접속 IP가 바뀌면 관리 화면에서 갱신한다.
5. 이 구성에서는 80/443/3000/8000/5432를 인터넷에 공개하지 않는다. IPv6 규칙도 확인한다.
6. 외부로 나가는 Docker·패키지 다운로드, DNS, HTTPS, Tunnel 7844/UDP 또는 TCP, 푸시 서비스 통신은 허용해야 한다.

[Lightsail 고정 IP](https://docs.aws.amazon.com/lightsail/latest/userguide/lightsail-create-static-ip.html), [Tunnel 외부 연결 포트](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-with-firewall/)

**[Mac]** 실제 IP와 키 파일로 바꾼다. 새 Mac 터미널에서는 다시 설정한다.

```bash
export OROT_AWS_IP=203.0.113.10
export OROT_SSH_KEY="$HOME/.ssh/orot-lightsail.pem"
chmod 600 "$OROT_SSH_KEY"
ssh -i "$OROT_SSH_KEY" "ubuntu@$OROT_AWS_IP"
```

`203.0.113.10`은 설명용 주소라 접속할 수 없다. 첫 SSH 호스트 키는 AWS 브라우저 SSH 등 별도 경로로 대조한다. `StrictHostKeyChecking=no`로 검사를 생략하지 않는다.

### 11.3 Ubuntu와 Docker 설치

**[AWS · SSH 접속한 서버]**

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl git make python3 unzip age nano
sudo install -d -m 0755 /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Docker 공식 APT 저장소를 등록한다.

```bash
sudo python3 - <<'PY'
from pathlib import Path
import subprocess
values = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
codename = values['VERSION_CODENAME'].strip('"')
arch = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip()
text = ('Types: deb\nURIs: https://download.docker.com/linux/ubuntu\n'
        f'Suites: {codename}\nComponents: stable\nArchitectures: {arch}\n'
        'Signed-By: /etc/apt/keyrings/docker.asc\n')
Path('/etc/apt/sources.list.d/docker.sources').write_text(text)
PY
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
exit
```

**[Mac]** 그룹 변경이 반영되도록 다시 접속한다.

```bash
ssh -i "$OROT_SSH_KEY" "ubuntu@$OROT_AWS_IP"
```

**[AWS]**

```bash
docker version
docker compose version
docker run --rm hello-world
mkdir -p /home/ubuntu/OROT
chmod 700 /home/ubuntu/OROT
```

Docker 그룹은 사실상 호스트 관리 권한을 가진다. 일반 사용자를 추가하지 않는다. Mac의 ARM용 venv·node_modules를 AWS로 복사하지 않고 AWS CPU에 맞는 이미지를 그곳에서 빌드한다. [Docker 공식 Ubuntu 설치](https://docs.docker.com/engine/install/ubuntu/)

<a id="step-12"></a>

## 12. AWS에 소스·설정·이미지 준비

### 12.1 배포 소스 확정

**[Mac · 프로젝트 루트]**

```bash
git status --short
git diff --check
make lint
make test
```

GitHub CI의 Web checks도 통과한 revision을 고른다. 생성한 `compose.hosted.yaml`, 두 `infra` 스크립트와 ignore 변경도 검토 후 커밋한다. 기존 미커밋 변경을 무조건 포함하지 않는다. `git status --short`가 빈 상태를 기준으로 한다. 직접 커밋할 때는 `git add -p`로 기존 변경을 검토하고, 새 운영 파일은 경로를 지정해 추가한다. 아래는 검토가 끝난 운영 파일만 추가하는 예시다.

```bash
git add compose.hosted.yaml infra/orot-hosted-start.sh infra/orot-portable-backup.sh .gitignore .dockerignore
git diff --cached --stat
git commit -m "Configure OROT hosted deployment and encrypted backups"
```

관련 앱 변경이 남아 있다면 그것도 검토·검증한 뒤 별도 커밋한다. 테스트한 소스와 실제 아카이브 내용이 일치해야 한다.

```bash
git cat-file -e HEAD:compose.hosted.yaml
git cat-file -e HEAD:infra/orot-portable-backup.sh
git ls-files .env .env.tunnel
mkdir -p backups/migration
chmod 700 backups/migration
git rev-parse HEAD > backups/migration/source-revision.txt
git archive --format=tar.gz -o backups/migration/orot-source.tar.gz HEAD
```

`git ls-files`는 출력이 없어야 한다. 아카이브에는 커밋한 소스만 포함되며 현재 `.env`·DB·venv는 들어가지 않는다. AWS에 GitHub 쓰기 권한을 전달할 필요도 없다.

### 12.2 SSH로 전송

**[Mac]** AWS 대상 디렉토리가 비어 있는 최초 설치에만 아카이브를 푼다.

```bash
scp -i "$OROT_SSH_KEY" backups/migration/orot-source.tar.gz \
  backups/migration/source-revision.txt "ubuntu@$OROT_AWS_IP:/home/ubuntu/"
scp -i "$OROT_SSH_KEY" .env .env.tunnel "ubuntu@$OROT_AWS_IP:/home/ubuntu/OROT/"
```

**[AWS]**

```bash
cd /home/ubuntu/OROT
tar -xzf /home/ubuntu/orot-source.tar.gz
chmod 600 .env .env.tunnel
mkdir -p backups/migration
chmod 700 backups backups/migration
cp /home/ubuntu/source-revision.txt backups/migration/source-revision.txt
```

아카이브에는 `.git`이 없으므로 §9의 백업 스크립트는 `backups/migration/source-revision.txt`를 대신 읽는다. 해당 파일을 삭제하지 않는다. 별도 서버 측 소스 수정 없이 같은 스크립트를 사용한다.

토큰 파일을 AWS에 복사했지만 **아직 cloudflared를 시작하지 않는다.**

### 12.3 AWS 전용 로컬 설정 정리

**[AWS · 프로젝트 루트]** 여기의 `python3`는 OS Python이다. 앱 Python은 Docker 안에서 실행한다.

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('.env')
lines = [line for line in p.read_text().splitlines()
         if not line.startswith(('ENV_BACKUP_DIR=', 'ENV_BACKUP_KEYCHAIN_SERVICE='))]
lines.append('ENV_BACKUP_DIR=backups/env')
p.write_text('\n'.join(lines) + '\n')
p.chmod(0o600)
PY
```

다음 값은 유지한다.

- `PUBLIC_WEB_URL=https://기존과-동일한-실제-도메인`
- 동일한 VAPID 공개키·개인키, 관리자 키, 필요한 Slack 웹훅.
- `POSTGRES_USER=orot`, `POSTGRES_DB=orot`, 기존 DB 비밀번호.
- Docker 내부 `DATABASE_URL=postgresql+asyncpg://…@postgres:5432/orot`.
- `POSTGRES_VOLUME_NAME=orot_postgres_data`、`POSTGRES_VOLUME_EXTERNAL=true`。

Docker가 빈 DB에 같은 역할·비밀번호를 만들기 때문에 이름을 바꾸지 않는다. Cloudflare 토큰도 같은 Tunnel의 값을 유지한다.

**[AWS]** cloudflared를 내려받고 AWS에서 확인한 digest를 저장한다.

```bash
docker pull cloudflare/cloudflared:latest
python3 - <<'PY'
from pathlib import Path
import subprocess
image = subprocess.check_output(['docker', 'image', 'inspect',
    'cloudflare/cloudflared:latest', '--format', '{{index .RepoDigests 0}}'], text=True).strip()
assert image.startswith('cloudflare/cloudflared@sha256:')
p = Path('.env')
lines = [line for line in p.read_text().splitlines() if not line.startswith('CLOUDFLARED_IMAGE=')]
p.write_text('\n'.join(lines + ['CLOUDFLARED_IMAGE=' + image]) + '\n')
PY
```

Mac에서 검증한 cloudflared와 버전이 달라지면 릴리스 변경을 확인한다. 이전과 의도하지 않은 메이저 업데이트를 함께 진행하지 않는다.

### 12.4 공개하지 않고 준비

**[AWS]** `dc` 함수를 정의한다.

```bash
set -o pipefail
dc() {
  docker compose -f compose.yaml -f compose.prod.yaml -f compose.hosted.yaml "$@"
}
dc config --quiet
docker volume create orot_postgres_data
dc build api collector web
dc up -d --wait postgres
```

빌드 중 메모리가 부족하면 사용량을 확인하고 더 큰 인스턴스나 별도 빌드 환경을 사용한다. 4GB에서 빌드가 반드시 성공한다는 보장은 없다.

이미 같은 볼륨이 있다면 초기 준비용 빈 볼륨인지 확인한다. 재실행을 위해 무조건 삭제하지 않는다.

<a id="step-13"></a>

## 13. 사전 DB 복원과 비공개 검증

### 13.1 Mac의 사전 덤프

운영 중에 만드는 사전 덤프는 동작 확인용이다. 최종 데이터는 §14에서 서비스를 멈춘 뒤 다시 덤프한다.

**[Mac · 프로젝트 루트]**

```bash
umask 077
dc exec -T postgres pg_dump -U orot -d orot -Fc --no-owner --no-acl \
  > backups/migration/rehearsal.dump
test -s backups/migration/rehearsal.dump
scp -i "$OROT_SSH_KEY" backups/migration/rehearsal.dump \
  "ubuntu@$OROT_AWS_IP:/home/ubuntu/OROT/backups/migration/"
```

**[AWS · 프로젝트 루트]** 데이터가 없는 준비용 DB에만 복원한다.

```bash
dc exec -T postgres pg_isready -h 127.0.0.1 -U orot -d orot
dc exec -T postgres pg_restore -U orot -d orot \
  --no-owner --no-acl --exit-on-error < backups/migration/rehearsal.dump
dc run --rm --no-deps api alembic current
dc up -d --wait api web
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/
dc ps
```

같은 revision을 옮기므로 사전 검증에서 DB 마이그레이션을 변경하지 않는다. `alembic current`와 Mac 버전이 다르면 소스·덤프 조합을 확인하고 다음 단계로 넘어가지 않는다.

collector와 cloudflared는 중지되어 있어야 한다. 이미 실행 중이라면 `dc stop collector cloudflared`로 멈추고 의도하지 않은 전송·공개가 없었는지 확인한다.

### 13.2 Mac에서 AWS 화면 확인

**[Mac · 별도 터미널]**

```bash
ssh -i "$OROT_SSH_KEY" -N \
  -L 13000:127.0.0.1:3000 -L 18000:127.0.0.1:8000 \
  "ubuntu@$OROT_AWS_IP"
```

- `http://127.0.0.1:13000`에서 AWS 피드를 확인한다.
- `http://127.0.0.1:18000/admin`에서 관리자 화면을 확인한다.
- 데이터를 수정·공개하지 않는다. 사전 복사본에서 수정한 내용은 최종 복원으로 사라진다.
- 이 주소에서 운영 도메인의 푸시를 시험하지 않는다. 화면·조회·DB 연결만 확인한다.
- 시험을 위해 `PUBLIC_WEB_URL`을 localhost로 바꿨다가 그대로 배포하지 않는다.

<a id="step-14"></a>

## 14. 최종 이전: Mac 중지 → AWS 활성화

### 14.1 반드시 지킬 전환 조건

**Mac과 AWS의 독립 DB를 같은 Tunnel로 동시에 공개하지 않는다.** 같은 토큰의 connector를 여러 곳에서 실행하면 Cloudflare가 여러 replica로 트래픽을 전달할 수 있다. 읽기·쓰기가 서로 다른 DB로 나뉠 수 있고, 두 collector의 DB별 잠금으로는 중복 발송을 방지할 수 없다. [Tunnel replicas](https://developers.cloudflare.com/tunnel/concepts/routing/)

짧은 중단 시간을 두고 전환한다. 절차를 먼저 읽고 AWS 빌드·사전 검증을 끝낸 뒤 공지·예약 시작이 몰리지 않는 시간에 진행한다. 전환 중 코드나 DB 버전을 업데이트하지 않는다.

### 14.2 운영 Mac 중지와 최종 덤프

**[Mac · 프로젝트 루트]** 관리자 편집을 중단한다. LaunchAgent 등록 상태를 확인한 뒤 실행한다.

```bash
launchctl disable "gui/$(id -u)/com.orot.stack"
launchctl bootout "gui/$(id -u)/com.orot.stack"
launchctl disable "gui/$(id -u)/com.orot.backup"
launchctl bootout "gui/$(id -u)/com.orot.backup"
touch .orot-host-disabled
dc stop cloudflared web collector api
```

등록되지 않은 agent에 bootout을 실행하면 오류가 난다. `launchctl print`로 미등록을 확인한 경우에만 넘어간다. 백업이 실행 중이면 종료를 확인한다. PostgreSQL은 덤프를 위해 켜 둔다.

```bash
umask 077
dc exec -T postgres pg_dump -U orot -d orot -Fc --no-owner --no-acl \
  > backups/migration/final.dump
test -s backups/migration/final.dump
shasum -a 256 backups/migration/final.dump > backups/migration/final.dump.sha256
```

전체 public 테이블의 행 수를 기록한다. 아래 출력에는 테이블 이름·행 수만 있고 키 값은 없다.

```bash
dc exec -T postgres psql -U orot -d orot -At -c \
  "SELECT format('SELECT %L, count(*) FROM %I.%I;', tablename, schemaname, tablename) FROM pg_tables WHERE schemaname='public' ORDER BY tablename;" \
  | dc exec -T postgres psql -U orot -d orot -At -F ',' -v ON_ERROR_STOP=1 \
  > backups/migration/final-counts.csv
scp -i "$OROT_SSH_KEY" backups/migration/final.dump \
  backups/migration/final.dump.sha256 backups/migration/final-counts.csv \
  "ubuntu@$OROT_AWS_IP:/home/ubuntu/OROT/backups/migration/"
```

§12 이후 키가 바뀌었다면 `.env`·`.env.tunnel`도 다시 전송하고 AWS 백업 경로·cloudflared digest를 재조정한다. 일반적으로 이전 중 키를 바꾸지 않으므로 재전송하지 않는다.

### 14.3 AWS 사전 복사본을 최종 데이터로 교체

**[AWS · 프로젝트 루트]** **현재 호스트가 AWS인지 반드시 확인한다.** 다음 dropdb는 AWS 리허설 DB를 교체하는 명령이다. Mac에서 실행하지 않는다.

```bash
pwd
hostname
dc stop cloudflared web collector api
sha256sum -c backups/migration/final.dump.sha256
```

검사 성공 후 실행한다. 아직 AWS에는 공개 트래픽이 들어오지 않는다.

```bash
dc exec -T postgres dropdb -U orot --force orot
dc exec -T postgres createdb -U orot -O orot orot
dc exec -T postgres pg_restore -U orot -d orot \
  --no-owner --no-acl --exit-on-error < backups/migration/final.dump
```

복원 실패 시 다음으로 넘어가지 않는다. 최종 덤프와 Mac 원본이 보존되어 있으므로 §16으로 복구한다.

```bash
dc exec -T postgres psql -U orot -d orot -At -c \
  "SELECT format('SELECT %L, count(*) FROM %I.%I;', tablename, schemaname, tablename) FROM pg_tables WHERE schemaname='public' ORDER BY tablename;" \
  | dc exec -T postgres psql -U orot -d orot -At -F ',' -v ON_ERROR_STOP=1 \
  > backups/migration/aws-counts.csv
diff -u backups/migration/final-counts.csv backups/migration/aws-counts.csv
dc run --rm --no-deps api alembic current
dc up -d --wait api web
curl -fsS http://127.0.0.1:8000/healthz
```

행 수 diff는 출력이 없어야 한다. 전송 SHA-256, 복원 종료 코드, 전체 테이블 행 수, 마이그레이션 버전을 함께 확인한다. 행 수만으로 전체 데이터 내용이 같다고 판단하지 않는다.

### 14.4 같은 Tunnel을 AWS에서 시작

Cloudflare에서 Mac connector가 끊겼고 Mac의 `dc ps`에서도 cloudflared가 중지됐는지 확인한다. DNS·hostname·VAPID는 바꾸지 않는다.

**[AWS]**

```bash
dc up -d cloudflared
dc logs --tail=50 cloudflared
```

**[Mac 또는 휴대폰 외부 회선]** AWS 공개 사이트의 메인·상세·RSS·ICS를 확인한 다음 **AWS에서만** collector를 시작한다.

```bash
# AWS에서 실행
dc up -d collector
dc ps
```

Mac collector는 계속 중지한다. 보류 이벤트는 구현 규칙에 따라 처리되지만 중단 중 모든 이벤트의 발송을 보장하지는 않는다. 현재 알림에는 48시간 제한 등이 있으므로 중단 시간을 줄이고 배송 결과를 확인한다.

성공 확인:

- 같은 `https://운영-도메인`으로 접속된다.
- Cloudflare의 활성 connector는 AWS 쪽이다.
- AWS API/Postgres가 healthy다.
- 기존 일정·구독·배송 이력이 보존되어 있다.
- 해당 도메인에서 이전에 등록한 기기로 이용할 수 있다.
- 합의한 시험 공개를 1회 실행하고 배송 결과·기기 수신·클릭을 확인했다.
- Mac의 OROT 컨테이너를 멈춰도 사이트가 열린다. AWS 이전 완료 후에만 시험한다.

마지막 확인은 Mac의 `dc stop postgres` 등 남은 OROT 컨테이너 중지로 충분하다. 다른 프로젝트가 동작하는 Docker 전체를 무조건 중단할 필요는 없다.

<a id="step-15"></a>

## 15. AWS 자동 시작·외부 백업

### 15.1 systemd로 재시작 후 복구

**[AWS]** `sudo nano /etc/systemd/system/orot.service`로 아래 내용을 저장한다.

```ini
[Unit]
Description=OROT production stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ubuntu/OROT
ExecStart=/usr/bin/docker compose -f compose.yaml -f compose.prod.yaml -f compose.hosted.yaml --profile public up -d --no-build --wait
ExecStop=/usr/bin/docker compose -f compose.yaml -f compose.prod.yaml -f compose.hosted.yaml --profile public stop
TimeoutStartSec=300
TimeoutStopSec=120

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now orot.service
sudo systemctl status orot.service
```

oneshot 방식에서 `active (exited)`는 정상이다. 개별 컨테이너 상태는 `dc ps`로 확인한다. OS 재시작은 점검 시간을 잡고 실행한 뒤 SSH·systemd·컨테이너·외부 사이트를 순서대로 확인한다.

### 15.2 AWS 백업을 S3에 보관

먼저 AWS에서 §9의 백업 스크립트를 실행하고 암호화 파일을 scp로 Mac에 회수해도 서버 밖 복사본이 된다. 매일 자동으로 보관하려면 아래를 설정한다.

1. AWS S3에 고유한 백업 버킷 이름을 만든다. `orot-backup-ACCOUNT-RANDOM`은 예시이므로 실제 이름으로 바꾼다.
2. Public Access Block을 모두 유지하고 기본 암호화를 켠다.
3. 이 예시는 버전 관리를 끈 상태에서 `orot/` prefix의 객체를 90일 후 만료시키는 Lifecycle을 사용한다. 버전 관리를 켜면 이전 버전의 보존·삭제 정책도 설정해야 한다.
4. 업로드용 IAM 주체에는 아래 최소 권한만 부여한다. 일상 업로드 자격증명에는 삭제 권한을 주지 않는다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::REPLACE_WITH_BUCKET"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::REPLACE_WITH_BUCKET/orot/*"
    }
  ]
}
```

IAM 콘솔에서 Policies → Create policy → JSON으로 위 정책을 저장한다. Users에서 백업 전용 사용자를 만들고 이 정책만 연결한다. Security credentials에서 외부 서버용 액세스 키를 발급해 아래 대화형 설정에 입력한다. 기존 조직의 IAM 관리 절차가 있다면 그 절차를 따른다.

이 예시는 SSE-S3를 사용한다. SSE-KMS를 선택하면 KMS 권한이 별도로 필요하다. 복구용 읽기는 별도 관리자 권한으로 진행한다. [S3 IAM 정책](https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-policies-s3.html), [AWS CLI sync](https://docs.aws.amazon.com/cli/latest/reference/s3/sync.html)

이 Lightsail 구성에 EC2 instance profile이 자동으로 부여된다고 가정하지 않는다. 전용 IAM 사용자를 쓰는 경우 해당 용도의 액세스 키를 만들고 `aws configure`에 대화형으로 입력한다. 루트 키는 사용하지 않으며 자격증명 교체와 서버 폐기 후 폐기도 관리한다.

**[AWS · Ubuntu x86_64]** CLI를 설치한다. 다른 아키텍처이면 공식 aarch64 배포본을 사용한다.

```bash
cd /tmp
curl -fL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o orot-awscli.zip
unzip -q orot-awscli.zip -d orot-awscli-install
sudo ./orot-awscli-install/aws/install
aws --version
aws configure --profile orot-backup
```

대화형 입력: 전용 Access Key ID, Secret Access Key, 리전, 출력 형식 `json`. 키를 명령 인수에 쓰지 않는다. `~/.aws/credentials`는 600으로 제한한다. 공식 안내의 배포물 서명 검증도 참고한다. [AWS CLI 설치](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

**[AWS · `/home/ubuntu/OROT`]** `/home/ubuntu/OROT/.env.backup`을 만든다. age recipient는 공개 값이다.

```text
OROT_BACKUP_RECIPIENT=age1REPLACE_WITH_YOUR_PUBLIC_RECIPIENT
OROT_BACKUP_BUCKET=REPLACE_WITH_BUCKET
```

`infra/orot-backup-s3.sh`를 만든다.

```bash
#!/bin/bash
set -euo pipefail
cd /home/ubuntu/OROT
infra/orot-portable-backup.sh backups/encrypted "$OROT_BACKUP_RECIPIENT"
aws s3 sync backups/encrypted "s3://$OROT_BACKUP_BUCKET/orot/" \
  --profile orot-backup --sse AES256 --only-show-errors
# 업로드 성공 후에만 서버의 암호화 복사본을 7일 보관으로 정리한다.
find backups/encrypted -type f -name 'orot-*.tar.age' -mtime +7 -delete
```

`sudo nano /etc/systemd/system/orot-backup.service`로 저장할 내용:

```ini
[Unit]
Description=OROT encrypted backup to S3
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
User=ubuntu
SupplementaryGroups=docker
Environment=PATH=/usr/local/bin:/usr/bin:/bin
EnvironmentFile=/home/ubuntu/OROT/.env.backup
WorkingDirectory=/home/ubuntu/OROT
ExecStart=/bin/bash /home/ubuntu/OROT/infra/orot-backup-s3.sh
```

`sudo nano /etc/systemd/system/orot-backup.timer`로 저장할 내용:

```ini
[Unit]
Description=Daily OROT backup

[Timer]
OnCalendar=*-*-* 18:15:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

UTC 18:15는 한국 시각 다음 날 03:15다. 서버의 로컬 시간대에 의존하지 않고 명시한다.

```bash
chmod +x infra/orot-portable-backup.sh infra/orot-backup-s3.sh
chmod 600 .env.backup "$HOME/.aws/credentials"
sudo systemctl daemon-reload
sudo systemctl start orot-backup.service
sudo systemctl status orot-backup.service
sudo journalctl -u orot-backup.service --since today
sudo systemctl enable --now orot-backup.timer
systemctl list-timers orot-backup.timer
```

S3 콘솔에 실제 암호화 파일이 존재하고 Mac에서 내려받아 §9.5로 복호화·복원되는 것이 성공 기준이다. 서버에는 age 개인키를 두지 않고 공개 recipient만 둔다. timer 실패도 외부에서 파악한다. DB 디스크 스냅샷만을 유일한 복구 수단으로 삼지 않는다.

<a id="step-16"></a>

## 16. 이전 실패 시 복구

### 16.1 새 도메인의 Mac 공개가 실패한 경우

아직 AWS로 이전하지 않은 단계:

1. `dc stop cloudflared`로 새 공개를 중지한다.
2. `backups/domain-transition/before-domain.env`를 복원한다. 현재 DB 비밀번호와 맞는 백업인지 확인한다.
3. 기존 두 Compose 파일로 `up -d --build`한다. 기존 설정에는 cloudflared가 없으므로 먼저 명시적으로 중지한다.
4. 원래 Funnel로 돌아간다면 이전 포트를 확인하고 다시 활성화한다.
5. LaunchAgent를 백업 파일로 되돌리고 다시 등록한다.

DNS 설정 문제만 있다면 DB를 복원할 필요는 없다.

### 16.2 AWS 쓰기·발송 시작 전

최종 데이터 복원이나 비공개 확인이 실패했고, AWS가 쓰기나 발송을 시작하지 않은 경우다. Tunnel을 공개한 순간부터 사용자가 구독을 등록할 수 있으므로, 공개 이후에는 쓰기가 없었다고 확인할 수 없는 한 §16.3을 따른다.

**[AWS]**

```bash
cd /home/ubuntu/OROT
dc stop cloudflared collector web api
```

AWS에 이미 `orot.service`를 등록했다면 `sudo systemctl disable --now orot.service`도 실행한다.

**[Mac]**

```bash
cd /Users/jaehyeon/PersonalProjects/OROT
rm .orot-host-disabled
dc --profile public up -d --no-build --wait
launchctl enable "gui/$(id -u)/com.orot.stack"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.orot.stack.plist"
launchctl enable "gui/$(id -u)/com.orot.backup"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.orot.backup.plist"
```

Cloudflare는 다시 연결한 Mac으로 요청을 보낸다. Mac DB에 전환 직전 원본이 있으므로 재복원은 필요 없으며 도메인도 유지한다.

### 16.3 AWS 쓰기·푸시 발송 시작 후

**이전 Mac DB를 그대로 다시 공개하지 않는다.** 새 구독·변경·배송 이력이 사라지고 같은 이벤트를 다시 보낼 수 있다.

1. AWS의 cloudflared·collector·web·api를 중지한다.
2. 등록된 `orot.service`와 `orot-backup.timer`는 중지·비활성화해 자동 재개를 막는다.
3. systemd 중지로 PostgreSQL도 멈췄다면 `dc up -d --wait postgres`로 DB만 다시 시작한다. AWS 현재 DB를 같은 pg_dump 형식으로 `backups/migration/failback.dump`에 저장한다.
4. Mac의 이전 DB도 별도 덤프로 보관한다.
5. AWS 덤프를 scp로 Mac에 가져온다.
6. **Mac 앱·collector가 중지된 상태에서** Mac DB를 drop/create하고 AWS 원본을 복원한다.
7. §14의 행 수·버전·복원 종료 코드 검사를 수행한다.
8. AWS connector가 중지됐는지 확인하고 Mac을 다시 공개한다.

주요 명령:

```bash
# AWS: 앱·systemd 중지 후 DB만 실행
dc up -d --wait postgres
umask 077
dc exec -T postgres pg_dump -U orot -d orot -Fc --no-owner --no-acl \
  > backups/migration/failback.dump
```

```bash
# Mac: 데이터 회수. Mac 프로젝트 루트에서 dc 함수를 정의한 상태여야 한다.
scp -i "$OROT_SSH_KEY" \
  "ubuntu@$OROT_AWS_IP:/home/ubuntu/OROT/backups/migration/failback.dump" \
  backups/migration/failback.dump
dc up -d --wait postgres
dc exec -T postgres pg_dump -U orot -d orot -Fc --no-owner --no-acl \
  > backups/migration/mac-before-failback.dump
dc exec -T postgres dropdb -U orot --force orot
dc exec -T postgres createdb -U orot -O orot orot
dc exec -T postgres pg_restore -U orot -d orot --no-owner --no-acl --exit-on-error \
  < backups/migration/failback.dump
```

복원 성공 후 §16.2의 Mac 재개 절차를 따른다. 이전 후 마이그레이션을 적용했다면 DB뿐 아니라 대응 소스·이미지도 맞춰야 한다. 초기 이전 중에는 코드 업데이트를 함께 하지 않는다.

<a id="step-17"></a>

## 17. 증상별 해결표

| 증상 | 먼저 확인할 것 | 대응 |
|---|---|---|
| 도메인 이름 해석 실패 | NS·Cloudflare Active·hostname 레코드 | 등록기관 NS와 Cloudflare 값을 맞추고 기존 DNSSEC DS 확인 |
| HTTPS 인증서 오류 | 실제 hostname·Edge Certificate | Funnel 단순 CNAME 대신 Tunnel route와 인증서 활성화 확인 |
| Cloudflare 1033 등 연결 실패 | connector 실행 여부 | dc ps·로그·토큰·외부 7844 연결 확인 |
| Cloudflare 502 | connector에서 web으로 연결 | Service URL web:3000과 web/API 상태 확인 |
| 로컬은 열리지만 휴대폰은 실패 | hostname·Tunnel route | 외부 회선에서 DNS·HTTPS 확인. 관리 포트를 공개하지 않음 |
| 푸시 403 | Origin/Host·브라우저 권한·Cloudflare 규칙 | 같은 운영 도메인에서 구독. Host override·다른 출처 호출 확인 |
| 구독 주소에 localhost 표시 | PUBLIC_WEB_URL | 올바른 Compose 설정으로 api/collector/web 재생성 |
| 이전 후 빈 데이터 | engine/context·볼륨·DB 이름 | 초기화하지 말고 정확한 덤프·접속 대상 확인 |
| external volume not found | 현재 호스트·Docker context | Mac 기존 엔진 확인. 최초 AWS에서만 volume create |
| 코드 변경 미반영 | hosted에 소스 마운트 없음 | 해당 서비스 재빌드·재생성 |
| 웹은 열리지만 알림 없음 | collector·VAPID·구독·배송 기록 | 로그·상태별 건수 확인. 시험 전 대상자에게 안내 |
| Mac 재부팅 후 미복구 | 로그인·Colima·LaunchAgent | 로그인 후 agent·시작 로그 확인 |
| AWS SSH 실패 | 고정 IP·키·22 허용 IP | 본인 IP 변경·브라우저 SSH 접근 조건 확인 |
| dc 명령 없음 | 새 터미널 | §2 함수 재정의 |
| .env.tunnel not found | 파일 생성·전송 | §5에서 토큰 비표시 입력. 빈 토큰으로 진행하지 않음 |
| age 복호화 실패 | 생성 당시 개인키 | 새 키로 기존 백업을 복호화할 수 없음. 보관한 원래 키 사용 |
| S3 AccessDenied | 버킷·prefix·IAM·암호화 | 전용 profile의 List/Put 권한과 SSE-S3 대조 |
| 백업은 있지만 복구 실패 | dump·설정·키·revision | 운영 DB 대신 §9.5 격리 DB에서 원인 확인 |

<a id="step-18"></a>

## 18. 완료 체크리스트와 참고 자료

### Mac + 사용자 도메인 완료 조건

- [ ] 도메인 갱신·MFA·계정 복구 수단을 설정했다.
- [ ] Cloudflare DNS가 Active이고 외부 회선에서 HTTPS로 열린다.
- [ ] 공개 대상은 web:3000뿐이며 API·DB는 loopback이다.
- [ ] 공개 /admin은 404이고 로컬/SSH 관리는 작동한다.
- [ ] 세 Compose 파일로 운영하며 API reload·소스 마운트를 제거했다.
- [ ] 기존 Funnel 사용자에게 새 도메인 구독을 안내했다.
- [ ] 실제 푸시 수신과 클릭 주소를 확인했다.
- [ ] Mac 로그인 후 자동 시작과 외부 접속을 검증했다.
- [ ] DB·.env·.env.tunnel 암호화 백업과 격리 복원을 확인했다.
- [ ] 개인키와 백업이 Mac 한 곳에만 존재하지 않는다.

### AWS 이전 완료 조건

- [ ] 같은 소스 revision·PostgreSQL 메이저 버전으로 사전 복원했다.
- [ ] Mac 중지 후 최종 덤프를 AWS에 복원하고 체크섬·행 수를 비교했다.
- [ ] Tunnel connector와 collector가 AWS에서만 실행 중이다.
- [ ] 같은 hostname·VAPID 키·배송 이력을 유지했다.
- [ ] Mac의 OROT을 멈춰도 사이트가 열린다.
- [ ] AWS 재부팅 복구와 관리용 SSH를 확인했다.
- [ ] S3에 실제 백업이 있고 외부 기기에서 복원했다.
- [ ] rollback/failback 조건을 이해하고 이전 볼륨을 보존했다.
- [ ] 비용·도메인 갱신·백업 보존·복구 키 관리를 설정했다.

### 보관할 운영 기록

도메인, 등록기관, 갱신일, Cloudflare zone/Tunnel ID, 현재 운영 호스트, AWS 리전·인스턴스, 소스 revision, 백업 위치, 최종 복원 시험일을 기록한다. 키·토큰 자체는 문서에 쓰지 않고 비밀번호 관리자의 보관 항목 이름만 적는다.

### 이 문서 작성 시 검증한 범위

- 셸 코드 블록의 `bash -n` 문법 검사와 내장 Python 코드의 구문 검사.
- JSON, LaunchAgent plist, systemd INI 형식과 목차 링크 검사.
- 실제 비밀 값 대신 임시 값을 사용한 Docker Compose 병합 검사: 다섯 서비스, 앱 소스 마운트와 API reload 제거, loopback 포트 유지, Tunnel에만 토큰 전달 확인.
- 도메인 구매·DNS·Tunnel 계정 생성·AWS 배포·백업 복호화/DB 복원은 실제 실행하지 않았다. 본문의 완료 조건을 운영자가 해당 환경에서 검증해야 한다.

### 구현상 전제

현재 compose.yaml·compose.prod.yaml·Dockerfiles·Makefile·infra·웹 중계·푸시/스케줄러 구현과 대조했다. 이후 코드가 변경되면 포트·환경 변수·마이그레이션·백업 형식을 다시 확인한다. Cloudflare/AWS 화면 명칭은 바뀔 수 있으므로 본문의 기능과 공식 자료를 대조한다.

- [Tailscale Funnel](https://tailscale.com/docs/features/tailscale-funnel)
- [Cloudflare DNS full setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/)
- [Cloudflare Tunnel setup](https://developers.cloudflare.com/tunnel/setup/)
- [Cloudflare Tunnel run parameters](https://developers.cloudflare.com/tunnel/reference/run-parameters/)
- [Cloudflare Tunnel routing/replicas](https://developers.cloudflare.com/tunnel/concepts/routing/)
- [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Lightsail pricing](https://aws.amazon.com/lightsail/pricing/)
- [Lightsail static IP](https://docs.aws.amazon.com/lightsail/latest/userguide/lightsail-create-static-ip.html)
- [AWS CLI install](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [age encryption](https://github.com/FiloSottile/age)
- [W3C Push API](https://www.w3.org/TR/push-api/)
