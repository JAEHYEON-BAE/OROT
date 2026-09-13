# OROT 모바일 앱에 도메인이 필요한가: 구매 없이 Mac mini·AWS로 운영하는 방법

작성일: **2026-09-13**. 현재 OROT 소스와 공식 서비스 문서를 기준으로 작성했다.

## 먼저 답부터

**모바일 앱을 만들거나 배포하고, 그 앱의 서버를 운영하기 위해 사용자 소유 도메인을 반드시 구입할 필요는 없다.**

현재처럼 Mac mini와 Tailscale Funnel이 제공하는 HTTPS 주소를 사용할 수 있다. 이후 AWS로 옮겨서도 Funnel을 사용하거나, AWS의 관리형 서비스가 제공하는 기본 HTTPS 주소를 사용할 수 있다.

다만 아래 세 가지는 별개의 문제다.

1. **주소**: 앱이 어느 서버로 요청을 보낼 것인가?
2. **실행 환경**: API·DB·알림 스케줄러를 어느 컴퓨터에서 계속 실행할 것인가?
3. **앱 배포**: 사용자가 모바일 앱을 어디에서 설치할 것인가?

도메인을 구입하면 주로 1번의 주소를 직접 관리할 수 있다. 구입만으로 서버가 상시 실행되거나 앱이 App Store에 배포되지는 않는다.

앞서 작성한 [도메인·Mac mini·AWS 이전 가이드](HOSTING_GUIDE.ko.md)는 **사용자 도메인을 선택했을 때의 실행 절차**다. 그 구성이 모바일 앱 개발의 필수 조건이라는 뜻은 아니다. 도메인 구매를 미루기로 했다면 해당 문서의 Cloudflare DNS·Tunnel 등록 단계를 실행할 필요가 없다.

이 문서는 새 도메인이나 AWS 리소스를 생성하지 않으며, 현재 운영 설정도 변경하지 않는다.

## 목차

1. [현재 OROT은 어떤 종류의 앱인가](#current-app)
2. [네이티브 앱에서 실제로 호스팅하는 것](#what-is-hosted)
3. [도메인 구매와 HTTPS 주소의 차이](#domain-and-address)
4. [현재 Mac mini + Funnel을 계속 사용해도 되는가](#mac-funnel)
5. [네이티브 앱이 Funnel 서버에 연결하려면](#native-api)
6. [도메인 구매 없이 AWS에서 운영하는 선택지](#aws-options)
7. [IP 주소만으로 연결할 수 있는가](#ip-address)
8. [푸시 알림에 도메인이 필요한가](#push)
9. [App Store 배포·지원 페이지·링크](#app-store)
10. [서버 이전 시 실제로 바뀌는 것](#migration)
11. [도메인을 구매하면 생기는 이점과 한계](#tradeoffs)
12. [OROT에 권하는 진행 순서](#recommendation)
13. [질문별 빠른 답변](#faq)
14. [확인 범위와 공식 자료](#sources)

<a id="current-app"></a>

## 1. 현재 OROT은 어떤 종류의 앱인가

‘모바일 앱’이라는 표현에는 서로 다른 형태가 포함된다.

| 구분 | 현재 OROT의 PWA | 향후 SwiftUI 등 네이티브 앱 |
|---|---|---|
| 설치·접속 | 웹 주소에 접속하거나 홈 화면에 추가 | App Store·TestFlight 등으로 앱 설치 |
| 화면 실행 | 브라우저·웹 앱 환경 | 기기에 설치한 앱 프로그램 |
| 화면 코드 전달 | 웹 서버가 제공 | 앱 배포 과정에서 기기에 설치 |
| 서버 데이터 조회 | 웹 서버와 API를 통해 처리 | 앱이 HTTPS API를 직접 호출 |
| 현재 알림 방식 | Web Push | iOS라면 APNs 구현 필요 |
| 사용자 도메인 구매 | 필수 아님 | 필수 아님 |

**현재 저장소에는 `apps/api`, `apps/collector`, `apps/web`이 있고, `apps/ios`는 없다.** PWA·Web Push는 구현되어 있지만 네이티브 iOS 앱과 APNs는 블루프린트의 후속 계획이다.

따라서 ‘앞으로 주력 서비스를 모바일 앱으로 만들겠다’는 방향과 ‘현재 네이티브 앱이 운영되고 있다’는 상태는 구분해야 한다.

지금은 다음 두 경로 중 하나로 진행할 수 있다.

- PWA를 모바일 서비스로 계속 검증하면서, 나중에 네이티브 앱을 만든다.
- 현재 API와 데이터 모델을 활용해 네이티브 앱을 개발하고, 웹은 안내·보조 화면으로 유지한다.

어느 경로든 도메인 구매부터 해야 개발이 시작되는 것은 아니다.

<a id="what-is-hosted"></a>

## 2. 네이티브 앱에서 실제로 호스팅하는 것

네이티브 앱의 화면 프로그램은 사용자 기기에 설치된다. Mac mini에서 iPhone 화면 프로그램 자체를 계속 실행해 사용자의 화면으로 보내는 구조가 아니다.

OROT처럼 최신 일정과 알림이 필요한 앱에서는 다음 서버 구성 요소를 운영한다.

| 구성 요소 | 역할 | 계속 실행할 필요 |
|---|---|---|
| API | 발매 일정 조회, 앱의 등록 요청 처리 | 사용자가 요청할 때 응답할 수 있어야 함 |
| PostgreSQL | 일정·구독·이벤트·배송 이력 저장 | API와 스케줄러가 사용할 수 있어야 함 |
| collector/스케줄러 | 시간이 된 이벤트 생성과 알림 발송 | 현재 구현은 상주 실행 필요 |
| 웹 | PWA, RSS·캘린더, 웹에서 열리는 상세 페이지 | 해당 웹 기능을 유지한다면 필요 |
| 앱 배포 시스템 | 서명한 앱 빌드 배포·업데이트 | App Store/TestFlight 등 별도 체계 |

```text
사용자 iPhone
  └─ 설치한 OROT 앱
       ├─ 화면 표시: iPhone에서 실행
       └─ 일정 요청: HTTPS → OROT API → PostgreSQL

OROT 스케줄러 → 알림 서비스 → 사용자 기기
```

App Store에 앱을 올려도 Apple이 OROT의 PostgreSQL과 Python API를 대신 운영해 주는 것은 아니다. 반대로 AWS에 API를 올려도 iOS 앱이 자동으로 App Store에 등록되지는 않는다.

Mac mini가 꺼지면 설치한 네이티브 앱 자체는 기기에 남아 실행될 수 있다. 그러나 별도 오프라인 기능을 구현하지 않았다면 새 일정 조회나 서버 연동은 실패한다. 새 알림 생성·발송도 중단된다. ‘앱이 실행된다’와 ‘서비스를 정상 이용할 수 있다’는 별개다.

<a id="domain-and-address"></a>

## 3. 도메인 구매와 HTTPS 주소의 차이

앱이 서버에 연결하려면 주소가 필요하다. 그 주소의 도메인을 반드시 직접 소유해야 하는 것은 아니다.

| 예시 | 직접 도메인 등록 필요 | 설명 |
|---|---|---|
| `https://api.orot.io` | 필요 | `orot.io` 소유자가 설정하는 주소 |
| `https://장비명.테일넷명.ts.net` | 불필요 | Tailscale이 제공하는 이름 |
| `https://서비스명.식별자.리전.cs.amazonlightsail.com` | 불필요 | Lightsail Container Service 기본 주소 |
| `https://API_ID.execute-api.REGION.amazonaws.com` | 불필요 | API Gateway 기본 주소 |
| `https://고정-IP` | 도메인 등록 불필요 | 해당 IP에 유효한 인증서와 직접 운영 구성이 필요 |

표의 주소는 형식 예시다. 실제 계정에서 발급된 주소를 사용해야 한다.

‘도메인 구매 없이 운영’은 보통 **제공자가 관리하는 도메인 이름을 사용하는 것**이다. 인터넷 이름 체계 자체를 전혀 쓰지 않는다는 뜻은 아니다.

일반적인 iOS 네트워크 통신에서는 ATS(App Transport Security)의 요구를 충족하는 HTTPS와 신뢰할 수 있는 서버 인증서를 사용하는 것이 기본이다. 인증서가 사용자 소유 도메인에 발급됐는지, 제공자의 기본 주소에 발급됐는지는 도메인 구매 여부와 다른 문제다. [Apple ATS 안내](https://developer.apple.com/documentation/security/preventing-insecure-network-connections)

또한 `orot.io`를 구매하면 `app.orot.io`, `api.orot.io` 등을 별도 등록비 없이 만들 수 있지만, 각 주소의 호스팅 비용까지 무료가 되는 것은 아니다.

<a id="mac-funnel"></a>

## 4. 현재 Mac mini + Funnel을 계속 사용해도 되는가

### 4.1 가능하다

현재 PWA를 모바일에서 사용하는 데 사용자 도메인 구매는 필요하지 않다. 이미 제공되는 Funnel HTTPS 주소에 접속하고 홈 화면에 추가하면 된다.

네이티브 앱도 공개된 HTTPS 서버에 연결할 수 있으므로, 필요한 API를 적절히 공개하면 Funnel 주소를 서버 주소로 사용할 수 있다.

Funnel 접속자는 Tailscale 앱을 설치하거나 같은 tailnet에 들어갈 필요가 없다. 반면 Tailscale Serve 또는 사설 Tailscale IP만 사용하는 구성은 본인 장비·내부 테스트용 접근과 구분해야 한다. [Funnel 공식 설명](https://tailscale.com/docs/features/tailscale-funnel), [Funnel과 공유 비교](https://tailscale.com/docs/reference/funnel-vs-sharing)

### 4.2 연결 구조

```text
사용자 모바일 기기
  → Funnel의 공개 HTTPS 주소
  → Mac mini에서 실행하는 서비스
  → API / DB / 스케줄러
```

이 방식의 장점은 도메인 등록과 별도 HTTPS 인증서 운영을 먼저 할 필요가 없고, 지금 환경을 활용해 빠르게 검증할 수 있다는 것이다.

한계도 분명하다.

- Mac mini·Docker·인터넷이 정상이어야 한다.
- 절전·로그아웃·재부팅·정전이 서비스 가용성에 영향을 준다.
- Funnel은 설정할 수 없는 대역폭 제한이 있으며, 공식 문서상 베타 상태다.
- 공개 이름은 Tailscale의 `ts.net` 범위에 속한다.
- 장비·테일넷 이름 또는 서비스 제공 방식 변경에 따른 주소 관리가 필요하다.

[Funnel의 지원 범위와 제한](https://tailscale.com/docs/features/tailscale-funnel)

이 한계는 ‘앱 심사에서 Funnel 주소를 쓰면 무조건 거절된다’는 뜻이 아니다. 앱의 기능·정책 준수·서버 접근성이 별도로 평가된다. 심사 중에는 실제 백엔드가 접근 가능해야 한다. [Apple 앱 심사 지침](https://developer.apple.com/app-store/review/guidelines/)

### 4.3 현재 상태에서 계속 운영할 때 할 일

1. `tailscale funnel status`로 현재 공개 대상이 OROT 웹 3000인지 확인한다.
2. Mac의 API·DB 포트 8000/5432는 기존처럼 로컬 바인딩을 유지한다.
3. 휴대폰 셀룰러 회선에서 접속·일정 조회·구독을 확인한다.
4. Mac 로그인 후 Colima·컨테이너 자동 시작을 점검한다.
5. DB뿐 아니라 VAPID 등 설정의 백업·복원을 확인한다.
6. 기기에서 실제 알림과 클릭 결과를 확인한다.

이 단계에는 `orot.io` 구매나 Cloudflare 계정 생성이 필수로 들어가지 않는다.

<a id="native-api"></a>

## 5. 네이티브 앱이 Funnel 서버에 연결하려면

### 5.1 현재 공개 웹 주소가 모든 JSON API를 제공하지는 않는다

현재 OROT 웹은 Next.js 서버가 Docker 내부의 `http://api:8000`으로 데이터를 요청해 화면을 만든다. 외부로 공개되는 웹 경로에는 다음 기능이 있다.

- 피드·캘린더·음반 상세 웹 화면.
- `/v1/feed.rss`, `/v1/releases.ics`.
- `/api/push/public-key`, `/api/push/subscribe`의 Web Push 중계.

그러나 현재 웹 라우트에 네이티브 앱이 사용할 **전체 JSON API의 중계 경로는 없다.** 예를 들어 FastAPI 내부의 `/v1/releases`가 존재해도, 웹만 공개한 Funnel 주소에 같은 경로를 붙이면 자동으로 API 응답이 나오는 것은 아니다.

따라서 도메인 구매 없이 네이티브 앱을 개발할 수 있지만, **현재 웹 서버를 그대로 두고 앱의 base URL만 입력하면 모든 기능이 연결된다고 보면 안 된다.**

### 5.2 권장 공개 방식

다음 중 하나를 구현한다.

| 방식 | 구성 | OROT에서의 고려사항 |
|---|---|---|
| 필요한 웹 중계 추가 | 현재 웹에 앱용 JSON 중계 경로 추가 | 초기 변경 범위가 작을 수 있음 |
| 공개 게이트웨이 추가 | Nginx/Caddy 등에서 허용한 API 경로만 전달 | 공개·관리 경계를 명시하기 좋음 |
| 공개 API와 관리자 분리 | 사용자 API를 별도 서비스로 운영 | 규모가 커질 때 명확하지만 작업량 증가 |

초기에는 앱이 실제로 쓰는 일정 조회 경로를 명시적으로 허용하는 방식이 적합하다. 앱의 APNs 등록 API는 구현 후 별도로 검토한다.

```text
Funnel → 공개 게이트웨이
           ├─ 사용자 화면 → web
           ├─ 명시적으로 허용한 JSON 경로 → api
           └─ 관리자 경로 → 외부 전달하지 않음

관리자 → 로컬 또는 SSH 터널 → api:8000/admin
```

이 그림의 게이트웨이는 **제안 구조이며 현재 구현되어 있지 않다.** 라우팅 이름과 허용 메서드를 정하고 테스트해야 한다. 모든 `/v1/*`를 검토 없이 허용하는 것보다 실제 앱 계약을 기준으로 공개 범위를 정하는 편이 낫다.

### 5.3 피해야 할 연결 방법

- 네이티브 앱에서 `http://api:8000` 호출: `api`는 Docker 내부 서비스 이름이다.
- 실기기 앱에서 `http://localhost:8000` 호출: localhost는 일반적으로 그 모바일 기기 자체다.
- 기존 FastAPI 8000 전체를 Funnel로 바로 공개: 현재 같은 앱에 관리자 경로도 들어 있다.
- `ADMIN_API_KEY`를 앱에 내장: 앱 바이너리에 포함한 값은 비밀 관리자 자격증명으로 사용할 수 없다.
- 인증서 검증을 끄거나 모든 HTTP 통신을 허용해 배포: 주소 설정 문제의 해결책으로 삼지 않는다.

네이티브 HTTP 클라이언트는 브라우저의 CORS와 같은 제약을 그대로 적용받지 않지만, 그 사실이 사용자 인증·요청 검증·속도 제한을 대신해 주지는 않는다.

<a id="aws-options"></a>

## 6. 도메인 구매 없이 AWS에서 운영하는 선택지

### 6.1 AWS 가상 서버 + Funnel

현재 구조에서 가장 적은 개념 변화로 옮기는 후보다.

```text
모바일 앱/PWA → AWS 장비의 Funnel HTTPS 주소
                    → Lightsail 또는 EC2
                    → Docker의 web / api / collector / postgres
```

이 경우:

- 사용자 도메인 구매는 필요 없다.
- Mac mini는 꺼도 된다.
- AWS 서버 요금은 발생한다.
- Tailscale/Funnel 의존성은 계속 남는다.
- 네이티브용 API 공개 경계는 §5처럼 준비해야 한다.

진행 순서는 다음과 같다.

1. Lightsail 또는 EC2에 Linux 서버를 만든다.
2. Docker·운영 설정·백업을 준비한다.
3. 서버를 본인의 Tailscale 네트워크에 추가한다.
4. 서버의 Tailscale 이름과 실제 발급 주소를 확인한다.
5. 올바른 웹/게이트웨이 포트를 Funnel에 연결한다.
6. DB·구독·키·배송 기록을 복사하고 새 주소에서 시험한다.
7. 최종 전환 때 기존 Mac의 쓰기와 스케줄러를 중지한다.
8. 새 서버만 운영하고, 앱/PWA의 주소 변경을 반영한다.

**새 AWS 장비에 같은 설정을 했다고 기존 Mac의 Funnel URL이 그대로 유지되는 것은 아니다.** 이름 변경·장비 교체를 통한 기존 이름 재사용은 충돌과 인증서·DNS 상태까지 검증해야 한다. 이전부터 동일 URL이 유지된다고 가정하지 않는다.

AWS 장비의 Funnel이 Mac의 서비스를 다시 프록시하도록만 설정하면, Mac이 꺼졌을 때 여전히 장애가 난다. 독립 운영을 위해 API·DB·스케줄러까지 옮겨야 한다.

### 6.2 Lightsail Container Service의 기본 HTTPS 주소

AWS Lightsail에는 일반 가상 서버 인스턴스 외에 **Container Service**라는 별도 상품이 있다. 이 서비스는 다음 형식의 기본 HTTPS endpoint를 제공한다.

```text
https://<service-name>.<random-guid>.<aws-region>.cs.amazonlightsail.com
```

사용자 도메인을 연결하지 않고도 이 주소로 서비스에 접속할 수 있다. [Lightsail Container Service 공식 FAQ](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-containers.html)

OROT에 적용할 때는 다음을 설계해야 한다.

- 웹/게이트웨이를 public endpoint로 지정.
- API와 collector의 컨테이너 실행·통신·재시작 구성.
- PostgreSQL은 영속성이 보장되는 별도 DB로 운영.
- 컨테이너 파일시스템에 현재 DB 데이터를 넣으면 보존될 것이라고 가정하지 않기.
- 현재 Compose를 서비스 배포 설정으로 변환.
- 여러 노드로 확장할 경우 스케줄러 중복 실행·DB 잠금 검토.

**‘Lightsail 인스턴스를 만들면 자동으로 위 HTTPS 주소가 나온다’는 뜻은 아니다.** 일반 VM과 Container Service를 혼동하지 않아야 한다. [서비스 구조](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services.html)

### 6.3 API Gateway 기본 주소 + 별도 백엔드

API Gateway는 자체 도메인 없이 사용할 수 있는 기본 호출 주소를 제공한다.

```text
https://<api-id>.execute-api.<region>.amazonaws.com
```

API 종류와 배포 방식에 따라 경로에 stage가 붙을 수 있다. 실제 콘솔의 invoke URL을 사용한다. [API Gateway 호출 주소](https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-call-api.html)

다만 API Gateway는 OROT의 DB·collector를 대신 실행하는 제품이 아니다.

- API 요청을 처리할 Lambda 또는 HTTP/VPC 연결 백엔드가 필요하다.
- DB는 별도로 필요하다.
- 기존 상주 스케줄러는 그대로 둘 실행 환경이 필요하거나, 예약 실행 구조로 다시 설계해야 한다.
- 요청당 비용·연결 제한·인증·네트워크 구성을 검토해야 한다.

현재 Docker 프로젝트의 단순 이전보다 변경 범위가 클 수 있다. 도메인 등록비만 줄이려고 선택하기보다는 전체 운영 방식이 맞을 때 선택한다.

### 6.4 CloudFront 기본 주소 + 원본 서버

CloudFront distribution은 기본 `*.cloudfront.net` 주소로 HTTPS를 제공할 수 있다. 별도 도메인 없이 앞단 주소로 사용할 수 있다. [Lightsail distribution의 기본 HTTPS 주소](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-cdn-distributions.html)

하지만 CloudFront는 원본 API·DB·스케줄러를 실행하지 않는다. AWS 원본 서버가 별도로 있어야 한다. JSON API·구독 요청에 대해 캐시·메서드·헤더·쿠키 전달과 원본 접근을 정확히 설계해야 한다. 앞단 HTTPS만 보고 원본 구간의 보안까지 완성됐다고 판단하지 않는다.

### 6.5 선택지 비교

| 구성 | 도메인 구매 | Mac 종료 가능 | 제공자 HTTPS 주소 | 현재 구조 변경량에 대한 판단 |
|---|---|---|---|---|
| Mac + Funnel | 불필요 | 불가 | 있음 | PWA는 현재 방식 유지 |
| AWS VM + Funnel | 불필요 | 가능 | 있음 | 상대적으로 적음 |
| Lightsail Container Service + 별도 DB | 불필요 | 가능 | 있음 | 중간 이상 |
| API Gateway + 백엔드/DB/스케줄러 | 불필요 | 가능 | 있음 | 중간~큼 |
| CloudFront + 원본 서버 | 불필요 | 가능 | 있음 | 전달·보안·캐시 설계 추가 |
| AWS VM의 공인 IP만 확보 | 불필요 | 가능 | HTTPS가 자동 완성되지는 않음 | 직접 TLS·접속 구성 필요 |
| 사용자 도메인 + 임의 서버 | 필요 | 서버 위치에 따름 | 인증서/접속 구성 필요 | 대신 공개 주소를 직접 관리 |

변경량은 현재 OROT 구조를 기준으로 한 판단이며 실제 배포 검증 결과가 아니다. 요금은 서버·DB·전송량·로그·백업 등 선택한 자원에 따라 별도로 발생한다. ‘도메인 구매 없음’과 ‘전체 서비스 무료’를 혼동하지 않는다.

<a id="ip-address"></a>

## 7. IP 주소만으로 연결할 수 있는가

가능한 기술적 구성이 있지만 초기 운영의 우선 선택으로 권하지 않는다.

예를 들어 앱이 `https://고정-IP`로 요청하도록 만들 수 있다. 단, 그 IP 주소와 일치하고 앱이 신뢰하는 인증서가 필요하며 발급·갱신을 운영해야 한다. 사설 IP를 쓰면 사용자의 인터넷에서 접근할 수 없는 문제도 있다.

2026년에는 IP 인증서가 불가능하다는 설명이 정확하지 않다. Let's Encrypt는 IP 주소용 단기 인증서를 일반 제공하며, 이런 인증서의 짧은 유효기간에 맞춘 자동 갱신이 필요하다. [Let's Encrypt 공식 발표](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability)

OROT에서는 다음 이유로 제공자 HTTPS 주소 또는 사용자 도메인이 더 다루기 쉽다.

- IP가 바뀌면 앱에 들어 있는 주소를 바꿔야 한다.
- 인증서 발급·갱신·프록시 설정을 직접 책임져야 한다.
- 서버 이전·교체와 앱 배포가 강하게 연결된다.
- 무료로 제공되는 HTTPS endpoint가 있는 경우 직접 IP 인증서를 운영할 실익이 작다.

일반 EC2/Lightsail VM의 공인 IP나 기본 DNS 이름은 ‘내 앱에 맞는 신뢰 가능한 HTTPS 서버가 이미 완성됐다’는 의미가 아니다. 도메인 구매 없이 운영하려면 주소 외에 TLS·원본 서비스 연결까지 확인해야 한다.

<a id="push"></a>

## 8. 푸시 알림에 도메인이 필요한가

### 8.1 현재 Web Push

현재 OROT은 웹/PWA의 Web Push를 사용한다. 제공자의 Funnel HTTPS 주소에서도 이용할 수 있으므로 도메인 구매가 필수는 아니다.

```text
사용자 브라우저가 구독
  → OROT이 구독 정보 저장
  → collector가 푸시 서비스로 전송
  → 기기의 웹 앱이 알림 표시
```

주소가 바뀌면 웹 출처와 서비스워커 등록이 달라진다. 기존 Funnel 주소에서 사용자 도메인 또는 다른 기본 주소로 바꿀 때는 새 주소에서 다시 구독하도록 안내해야 한다. DB·VAPID 키를 그대로 옮기는 것만으로 새 웹 출처에 구독이 자동 생성되지는 않는다. [W3C Push API](https://www.w3.org/TR/push-api/)

PWA는 주소가 설치·구독과 직접 연결되므로, 장기적인 URL 안정성이 네이티브 앱보다 더 눈에 띄게 중요하다.

### 8.2 향후 iOS 네이티브 앱의 APNs

APNs를 이용한 네이티브 푸시는 다음과 같은 구조다.

```text
iOS 앱 → APNs 등록 → 기기 토큰 수신
  → OROT 서버에 토큰 등록

OROT 서버 → APNs 인증·전송 → iOS 기기
```

앱이 APNs에서 받은 토큰을 서버에 전달하고, 서버가 앱에 맞는 자격증명으로 APNs에 요청한다. 이 과정에서 OROT 소유의 `orot.io`가 반드시 필요한 것은 아니다. 앱이 서버의 제공자 HTTPS 주소로 토큰 등록 요청을 보낼 수 있다. [Apple APNs 등록 안내](https://developer.apple.com/documentation/usernotifications/registering-your-app-with-apns)

필요한 것은 앱 식별자·서명·Push capability·APNs 자격증명·토큰 저장 API·서버 발송 구현이다. 현재 VAPID/Web Push 키를 APNs 인증키로 재사용할 수는 없다.

네이티브 앱에서 서버 주소만 바뀌고 같은 앱 식별자·APNs 환경·자격증명과 데이터가 유지된다면, 웹 출처 변경처럼 도메인 변경만을 이유로 알림 권한을 다시 받아야 하는 구조는 아니다. 다만 APNs 토큰은 갱신될 수 있으므로 앱이 토큰을 서버에 재등록하는 흐름을 구현해야 한다.

또한 APNs 자격증명은 서버에 보관한다. App Store 앱에 APNs 개인키나 관리자 키를 내장하지 않는다.

<a id="app-store"></a>

## 9. App Store 배포·지원 페이지·링크

### 9.1 앱 배포와 도메인 등록은 별도다

네이티브 iOS 앱 배포에는 Apple 개발자 계정, 앱 식별자, 서명, 빌드 업로드, App Store Connect 정보와 심사 등이 필요하다. 도메인 등록이 이 과정을 대신하지 않는다.

Funnel 또는 AWS 기본 주소를 쓴다는 사실만으로 배포 가능 여부가 결정되는 것도 아니다. 앱의 실제 기능과 개인정보 처리, 심사 시 접근 가능한 서버를 준비해야 한다.

현재 PWA를 단순 웹뷰로 감싸는 것과 네이티브 기능을 구현하는 것은 별도 개발 선택이다. 도메인 선택만으로 앱의 최소 기능·심사 문제가 해결되지는 않는다.

### 9.2 개인정보처리방침·지원 주소

Apple은 앱의 지원 링크와 개인정보처리방침 링크 등을 요구한다. 이 때문에 웹 페이지 주소는 필요할 수 있지만, 그 주소가 반드시 직접 구입한 도메인이어야 한다는 뜻은 아니다. 공개적으로 접근 가능하고 실제 앱의 연락처·처리 내용을 제공하는 페이지를 준비한다. [Apple App Review 안내](https://developer.apple.com/app-store/review/), [개인정보 URL 설정](https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy)

예를 들어 GitHub Pages의 기본 `github.io` 주소로 지원·개인정보 안내 문서를 제공하고, 실제 API는 Funnel에 둘 수 있다. 이는 문서 호스팅과 API 운영을 나누는 방식이다. GitHub Pages가 API·DB·스케줄러까지 실행해 주는 것은 아니다. [GitHub Pages 설명](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)

지원 문서는 서버 장애 때도 접근할 수 있는 별도 호스팅에 두면 유용하다. 사용자에게 도메인 구매 여부보다 연락 가능한 지원 정보와 실제 동작이 더 중요할 수 있다.

### 9.3 앱으로 열리는 링크

음반 링크를 눌렀을 때 앱의 특정 상세 화면을 여는 기능을 원하면 URL 설계도 필요하다. iOS Universal Links는 관련 도메인의 연결 파일과 앱 entitlement를 구성해야 한다. 사용자 도메인만 가능한 것은 아니지만, 해당 호스트에서 필요한 파일을 제공하고 연결을 관리할 수 있어야 한다. [Apple Associated Domains](https://developer.apple.com/documentation/xcode/supporting-associated-domains)

이 기능에서 직접 관리하는 도메인은 장기적인 링크 유지에 유리하다. 그렇다고 앱 목록·상세·알림 기능을 시작하기 전에 반드시 도메인을 사야 한다는 뜻은 아니다.

<a id="migration"></a>

## 10. 서버 이전 시 실제로 바뀌는 것

### 10.1 구매하지 않은 제공자 주소를 사용할 때

예시:

```text
기존: https://mac-node.example-tailnet.ts.net
이전: https://aws-node.example-tailnet.ts.net
```

둘은 서로 다른 호스트다. 새 서버를 만들거나 리소스를 다시 생성하면 제공자 주소가 바뀔 수 있다.

네이티브 앱에서는 서버 주소를 한 곳에서 관리하도록 설계하고, 개발·시험·운영 환경을 분리한다. 운영 URL이 코드 여러 곳에 흩어지지 않게 한다.

앱 업데이트로 URL을 바꾼다면, 구버전 사용자가 계속 이전 서버를 찾는다는 점을 고려해야 한다. 이전 URL을 잠시 유지해 새 서버로 안전하게 중계하거나, 업데이트 기간을 두는 방식이 필요하다. 로그인·POST·기기 등록 API에는 단순 리다이렉트만 적용하면 충분하다고 가정하지 않는다.

원격 설정으로 주소를 내려주는 방법도 가능하지만, 그 설정을 어디에서 안전하게 받을지라는 최초 접속 문제가 남는다. 원격 설정을 추가하면 주소 의존성이 사라지는 것이 아니라 의존하는 위치가 달라진다.

### 10.2 자체 도메인을 사용할 때

```text
앱에 설정한 주소: https://api.orot.io

서버 1: Mac mini
서버 2: AWS

이름은 유지하고 DNS/프록시의 연결 대상을 전환
```

같은 hostname과 API 계약을 유지하면 서버 위치 변경만으로 앱을 다시 배포할 필요를 줄일 수 있다. 그러나 인증서·라우팅·데이터·호환성·전환 절차는 여전히 검증해야 한다.

이것이 모바일 서비스에서도 도메인이 갖는 가장 실용적인 가치다. 사용자가 주소를 직접 입력하느냐보다 **앱이 의존하는 주소를 장기적으로 통제할 수 있느냐**가 중요하다.

### 10.3 도메인 선택과 무관하게 반드시 옮길 것

- 발매 일정과 연관 데이터.
- 기기 구독 또는 향후 APNs 토큰.
- 이벤트·배송 기록: 중복 발송 방지에 필요.
- VAPID 또는 APNs 자격증명 등 관련 서버 설정.
- 관리자 자격증명과 운영 경보 설정.
- 같은 데이터 스키마에 맞는 소스·마이그레이션 버전.
- 백업과 복구 방법.

Mac과 AWS에 독립 DB를 두고 collector를 동시에 실행하면, 각 DB의 잠금만으로 중복 발송을 막을 수 없다. 최종 데이터를 옮기기 전에 기존 쓰기·발송을 멈추고 새 서버를 단독 활성화한다.

이전 후 쓰기가 발생한 AWS에서 문제가 생겼다면 오래된 Mac DB를 그대로 다시 공개하지 않는다. 새 구독·배송 기록을 포함한 최신 데이터를 회수한 뒤 복구해야 한다. 상세 데이터 전환 원칙은 기존 호스팅 가이드의 백업·전환·복구 절차를 참고하되, **그 문서의 Cloudflare용 명령을 Funnel 구성에 그대로 적용하지 않는다.**

<a id="tradeoffs"></a>

## 11. 도메인을 구매하면 생기는 이점과 한계

| 판단 항목 | 제공자 기본 주소 | 직접 소유한 도메인 |
|---|---|---|
| 초기 비용 | 도메인 등록비 없음 | 등록·갱신 비용 |
| 빠른 개발·시험 | 충분히 가능 | 가능 |
| App Store 앱 서버 사용 | 가능 | 가능 |
| 제공자·호스트 변경 | 주소 변경 대응이 필요할 수 있음 | 같은 주소 유지가 상대적으로 쉬움 |
| PWA 설치·구독 주소 유지 | 제공자 이름 유지에 의존 | 운영자가 관리 가능 |
| 지원·개인정보·공유 링크 | 제공자 주소로 가능 | 일관된 브랜드 주소 구성 |
| 서버 상시 실행 | 별도 서버 운영 필요 | 역시 별도 서버 운영 필요 |
| 도메인 만료 관리 | 제공자 계정·정책 의존 | 본인의 갱신·DNS·계정 관리 필요 |

도메인 비용이 아깝거나 아직 서비스 방향을 검증 중이라면 지금 사지 않아도 된다. 반대로 이미 이름을 확정했고 공개 사용자·앱 버전이 쌓이기 시작했다면 주소를 고정하는 편이 나중의 변경 비용을 줄일 수 있다.

`orot.io`만이 유일한 선택도 아니다. 모바일 서비스 주소의 안정성이 목적이라면 합리적인 등록·갱신 비용의 다른 도메인으로도 같은 기술적 효과를 얻는다. 특정 도메인의 현재 등록 가능 여부나 가격은 별도 실시간 조회 대상이다.

브랜드 이름 선점과 서버 호스팅 필요성도 분리할 수 있다. 원한다면 도메인만 확보하고 API는 계속 Funnel 주소로 시험할 수 있다. 그러나 구매하지 않았다고 개발을 멈출 이유는 없다.

<a id="recommendation"></a>

## 12. OROT에 권하는 진행 순서

### 단계 A: 지금은 구매 없이 모바일 사용성을 검증

- 현재 Mac mini + Funnel + PWA를 유지한다.
- 실제 발매 일정 등록, 예약·발매 알림, RSS·캘린더를 확인한다.
- 절전·재부팅·백업 복구를 점검한다.
- 사용자에게 보이는 핵심 기능과 등록 운영의 부담을 파악한다.

완료 기준은 도메인 구입이 아니라 실제 기기에서 서비스를 안정적으로 사용할 수 있는지다.

### 단계 B: 주력 앱이 네이티브라면 API 계약을 준비

- 앱에 필요한 조회·상세·구독 API를 정의한다.
- 공개 JSON API 경로를 추가하고 관리 경로와 분리한다.
- 서버 주소를 앱 설정 한 곳에서 관리한다.
- 네이티브 앱에서 일정 조회·오류·로딩·오프라인 상태를 구현한다.
- iOS 푸시는 APNs 등록·토큰 저장·발송·토큰 갱신을 구현한다.
- 지원·개인정보 문서와 배포 절차를 준비한다.

이 단계도 Funnel의 HTTPS 주소로 시작할 수 있다. 현재 웹 구독 UI를 그대로 네이티브 APNs 등록 기능으로 사용할 수 있는 것은 아니다.

### 단계 C: Mac 의존성을 없애야 할 때 AWS로 이전

예를 들어 장시간 정전·재부팅·개인 개발 작업 때문에 알림이 중단되는 일이 부담이 되면 클라우드 이전을 진행한다.

두 가지 우선 후보:

1. **변경을 줄이고 싶다:** AWS VM + Funnel. 도메인 없이 Docker 기반을 옮긴다.
2. **주소·실행 관리를 AWS 서비스로 묶고 싶다:** 기본 HTTPS endpoint가 있는 관리형 서비스와 별도 DB. 현재 Compose 변환 비용을 검토한다.

어느 쪽이든 DB·스케줄러가 AWS에 있어야 Mac을 끌 수 있다. 웹 화면만 AWS로 옮기면 충분하지 않다.

### 단계 D: 주소 안정성의 가치가 커질 때 도메인 결정

다음 상황이라면 구매를 다시 검토한다.

- App Store 정식 사용자가 늘어 구버전 URL 변경이 부담스럽다.
- API 제공자·호스트를 앞으로 여러 번 바꿀 가능성이 있다.
- PWA 구독·공유 링크를 장기간 유지하고 싶다.
- 지원·개인정보·서비스 소개 주소를 일관되게 제공하고 싶다.

이때 구매 여부를 결정해도 된다. 다만 도메인 없이 출시한 뒤 구매하면 이미 배포한 앱과 PWA를 새 주소로 옮기는 전환 작업은 발생한다.

**현재의 구체적인 권고:** 도메인 구입을 필수 과제로 두지 말고, Mac + Funnel에서 모바일 사용 흐름을 검증한다. 네이티브 앱이 우선이라면 다음 구현은 사용자용 JSON API 공개 경계와 앱/APNs 연결이다. 상시 가용성이 필요해지면 AWS로 옮기고, 공개 출시 전후에 주소 고정의 비용·효과를 판단한다.

<a id="faq"></a>

## 13. 질문별 빠른 답변

| 질문 | 답변 |
|---|---|
| 모바일 앱인데 도메인이 꼭 필요한가? | 직접 구입한 도메인은 필수가 아니다. 접근 가능한 서버 주소는 필요하다. |
| Funnel로 계속 운영할 수 있나? | 가능하다. PWA는 현재 방식으로, 네이티브 앱은 필요한 API를 추가 공개한 뒤 이용한다. |
| 모든 앱 사용자가 Tailscale을 설치해야 하나? | 공개 Funnel 접속에는 필요 없다. 사설 Serve 구성은 다르다. |
| Mac에서 앱 전체를 호스팅하나? | 네이티브 프로그램은 기기에 설치되고 Mac에는 백엔드를 운영한다. PWA는 웹 서버도 필요하다. |
| Mac을 끄면 어떻게 되나? | 서버 기능·새 일정 조회·새 알림 처리가 중단된다. 네이티브 앱의 로컬 기능은 구현에 따라 남는다. |
| 도메인 없이 AWS에서 운영할 수 있나? | 가능하다. AWS + Funnel 또는 관리형 서비스 기본 HTTPS 주소를 쓴다. |
| EC2 공인 IP만 받으면 HTTPS도 끝인가? | 아니다. 인증서와 서비스 연결을 별도로 구성하거나 제공자 HTTPS endpoint를 사용한다. |
| IP용 인증서는 불가능한가? | 가능하지만 발급·자동 갱신을 운영해야 한다. |
| 네이티브 푸시에 `orot.io`가 필요한가? | 아니다. APNs 설정·서버 구현이 필요하다. |
| App Store에 올리면 서버는 안 켜도 되나? | 아니다. 설치 배포와 백엔드 운영은 별개다. |
| 도메인을 사면 호스팅 요금이 없어지나? | 아니다. 서버·DB·백업 비용과 별개다. |
| `app.orot.io`를 쓰면 전용 앱 서버가 자동 생성되나? | 아니다. 이름을 실제 서비스에 연결해야 한다. |
| `api.orot.io`를 꼭 따로 만들어야 하나? | 아니다. 한 HTTPS 호스트의 경로로 웹과 API를 나눌 수도 있다. |
| 지금 도메인을 사지 않으면 나중에 AWS로 못 옮기나? | 옮길 수 있다. 주소 변경과 기존 앱 버전·PWA 구독 전환을 계획하면 된다. |

<a id="sources"></a>

## 14. 확인 범위와 공식 자료

### 저장소에서 확인한 사실

- 현재 앱 디렉토리는 API·collector·web이며 iOS 프로젝트는 없다.
- 공개 웹에는 일부 중계만 있고 네이티브용 JSON API 전체가 공개되어 있지 않다.
- 웹 서버의 내부 API 호출과 모바일 기기의 외부 API 호출은 다른 경로다.
- 현재 알림은 Web Push이고 네이티브 APNs는 후속 계획이다.

이 문서의 AWS 선택지는 공식 지원 기능을 바탕으로 정리한 설계안이며 OROT을 해당 서비스에 실제 배포하여 검증한 결과가 아니다. 실서버 배포나 현재 Funnel 상태 변경은 하지 않았다.

### 공식 참고 자료

- [Tailscale Funnel의 기능·제한](https://tailscale.com/docs/features/tailscale-funnel)
- [Funnel CLI](https://tailscale.com/docs/reference/tailscale-cli/funnel)
- [Apple ATS](https://developer.apple.com/documentation/security/preventing-insecure-network-connections)
- [Apple APNs 등록](https://developer.apple.com/documentation/usernotifications/registering-your-app-with-apns)
- [Apple 앱 심사 준비](https://developer.apple.com/app-store/review/)
- [Apple 개인정보 URL](https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy)
- [Apple Associated Domains](https://developer.apple.com/documentation/xcode/supporting-associated-domains)
- [Lightsail Container Service 기본 HTTPS](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-containers.html)
- [API Gateway 기본 호출 URL](https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-call-api.html)
- [Lightsail distribution 기본 HTTPS](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-cdn-distributions.html)
- [Let's Encrypt IP 인증서](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability)
- [W3C Push API](https://www.w3.org/TR/push-api/)
- [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
