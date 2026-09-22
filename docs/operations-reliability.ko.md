# OROT 호스트 운영 보강

2026-09-15 코드 기준. 호스트 등록·실제 Slack 수신·DB 복구·외부 백업 성공은 각각 별도로 확인한다.

## 운영 이미지

`compose.prod.yaml`은 API의 `--reload`와 API·collector 소스 마운트를 제거한다.
운영 중 소스 저장만으로 API가 재시작되거나, 공유 core가 서로 다른 시점으로 반영되지 않는다.
API·collector·웹 변경은 `make prod`로 재빌드해야 한다. 개발용 `make up`은 기존 마운트를 유지한다.
이 변경 자체가 무중단 배포를 제공하지는 않는다.

## Colima 복구

```sh
cd /Users/jaehyeon/PersonalProjects/OROT
colima status
colima start
```

`vz driver is running but host agent is not`이면 정상 `colima stop` 후 다시 시작할 수 있다.
강제 종료는 DB 프로세스 비정상 종료 위험이 있어 별도 승인 대상이다. `colima delete`·볼륨 삭제는 복구 방법으로 자동 실행하지 않는다.
VM이 복구되면 먼저 `make backup`으로 DB를 보존하고 코드 검증 후 `make prod`를 실행한다.

## 백업

```sh
infra/orot-backup.sh
```

DB와 환경 백업을 독립적으로 시도한다. 어느 하나라도 실패하면 exit 1이다.
성공한 종류만 `backups/status/db.ok`, `env.ok`를 갱신한다. 환경 백업의 검증된 원본 지문은
`env.sha256`에 기록하며 비밀 값은 기록하지 않는다. 자동 DB pruning은 제거했다.
보관 기간 정리는 기존 `make backup-prune`을 검토 후 수동 실행한다.

`env-backup.sh`는 마지막 암호화 파일을 복호화해 원본과 비교한다. mtime이 오래되었어도
내용이 달라졌으면 새 백업을 만든다. 임시 암호문을 검증한 뒤 `.env.enc`로 게시하고,
평문 임시 파일을 만들지 않는다. 새 파일 권한은 생성 순간부터 제한한다.
동일 파일을 재사용하더라도 복호화 검증이 먼저 성공해야 한다.

### SSH와 키체인

키체인 항목 존재와 암호 읽기 가능 여부는 다르다. SSH 세션에서 키체인이 잠겨 있거나
사용자 승인이 필요하면 항목이 존재해도 암호화가 실패할 수 있다. 오류 코드 36은 이 상황에서 관찰되었다.
Mac mini의 로그인 세션에서 키체인 접근을 확인한다. 원격 화면 공유로 직접 확인해도 된다.
필요하면 해당 사용자의 로그인 키체인을 대화형으로 잠금 해제한다. 비밀번호는 명령 인수·채팅·로그에 넣지 않는다.
기존 암호를 모른다고 `make backup-env-setup`으로 덮어쓰지 않는다. 과거 암호문 복구에 기존 암호가 필요하다.

외부 목적지는 사용자가 아직 정하지 않았다. 현재 `.env`에는 iCloud 경로가 남아 있지만,
이 설정만으로 동기화·원격 보관·복원 가능성을 보장하지 않는다. 목적지를 확정한 뒤
`ENV_BACKUP_DIR`과 복구용 암호의 별도 보관을 확인한다.

### 과거 평문 롤백 파일

현재 `.env` 백업은 과거 `original.env`의 대체물이 아니다. 이전 DB URL이나 키 값이 다를 수 있다.
정리하려면 기존 원본 자체를 별도 디렉터리에 암호화하고 복호화 동일성을 확인한 뒤,
정확한 그 원본 파일의 삭제를 승인받는다. DB 덤프와 검증 기록은 보존한다.
현재는 키체인 접근이 막혀 있어 `original.env`를 삭제하지 않았다.

## 호스트 감시와 launchd

```sh
# 상태만 검사: Slack 발송 없음
venv/bin/python -m orot_collector.host_monitor

# 등록 전 검토용 파일 생성: 호스트 등록이나 발송을 하지 않음
venv/bin/python infra/install-launchagents.py --output /tmp/orot-launchagents
plutil -lint /tmp/orot-launchagents/*.plist
```

- stack: 실패한 종료만 300초 간격으로 재시도. healthz 200이면 정상 종료한다.
- backup: 매일 04:00 실행. 실패 시 1시간 간격 재시도한다.
- monitor: 300초마다 loopback API·웹 공개 읽기 경로·collector 컨테이너 실행 상태를 확인한다.
  백업 성공 기록이 36시간을 넘거나 산출물이 없거나 현재 환경 지문이 달라지면 장애로 보고한다.

Slack 발송을 활성화하려면 승인 후 생성기에 `--notify`를 추가한다. 기존 SlackAlerter를 재사용한다.
기본값은 로그 진단만 수행하며 알림을 보내지 않는다. 성공적으로 전송한 장애만 상태 파일에 저장한다.
같은 장애는 억제하고, 회복되었다 재발하면 새로 알린다. 전송 실패는 다음 검사에서 재시도한다.
Slack 웹훅을 plist에 넣지 않는다. 프로젝트 `.env`에서 읽는다.

검토한 plist를 `~/Library/LaunchAgents/`에 복사하고 다음으로 등록한다. 이미 등록된 잡은
먼저 `launchctl bootout gui/$(id -u) <plist 경로>`로 내린 뒤 등록한다. GUI 사용자 세션이 있어야 한다.
코드 변경의 운영 이미지 빌드·검증을 마친 뒤 stack 잡을 등록한다.

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.orot.stack.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.orot.backup.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.orot.monitor.plist
```

의도적으로 서비스를 중단할 때는 stack 재시도와 monitor 잡도 함께 내려야 한다.
이 감시는 Mac 자체 종료, 로그인 전 상태, Funnel 외부 접속 단절, 살아 있지만 멈춘 collector까지
모두 감지하는 외부 uptime 서비스가 아니다. 호스트 외부 감시와 scheduler heartbeat는 후속 과제다.

## 발송과 CI

발송기는 세션 advisory lock을 잡은 상태에서 계획을 커밋한 뒤, 개별 HTTP 전송과 결과 커밋을 수행한다.
HTTP 중 트랜잭션을 잡지 않는다. 같은 구독은 순차, 서로 다른 구독은 최대 5개 병렬이며
45초 뒤 새 전송을 시작하지 않는다. 그때 진행 중인 요청은 완료를 기다린다.
이미 커밋한 SENT는 재발송하지 않지만, 프로세스·네트워크·DB 장애 시 진행 중인 전송은 중복될 수 있다.
500건/주기 상한은 그대로이므로 10,000명에 대한 1분 배포를 보장하지 않는다.

CI는 Python·웹·모바일 세 잡을 실행한다. OpenAPI와 모바일 생성 타입을 다시 만들어 차이를 검사한다.
PostgreSQL은 실제 마이그레이션 체인을 사용하며 CHECK·CASCADE·정렬·일괄 조회와 발송 커밋을 검증한다.
`alembic check`는 autogenerate가 지원하는 드리프트만 검사한다.

참고: [Alembic autogenerate 한계](https://alembic.sqlalchemy.org/en/latest/autogenerate.html),
[SQLAlchemy AsyncSession 동시성](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).
