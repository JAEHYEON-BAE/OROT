# OROT UI를 보면서 수정하는 방법

2026-09-14 기준. 이 문서는 실행 안내이며 문서를 읽는 것만으로 서버나 Simulator가 시작되지는 않는다.

## 모바일 앱: 편집기 + Simulator + Fast Refresh

현재 OROT에는 Expo development build가 있으므로 이 방법이 가장 빠르다. 화면 왼쪽에 편집기, 오른쪽에 Simulator를 놓고 코드를 저장한다. 레이아웃·글꼴·색상 변경이 Fast Refresh로 반영된다. 일부 변경은 상태가 초기화되거나 전체 화면이 다시 로드될 수 있다. [React Native 공식 안내](https://reactnative.dev/docs/fast-refresh)

```sh
cd /Users/jaehyeon/PersonalProjects/OROT/apps/mobile
npm exec --yes --package=node@22.23.2 -- npm run start:simulator
```

이 명령은 Simulator에 이미 설치된 개발 앱을 연다. 기기에 OROT이 없다면 최초 한 번 다음 명령으로 빌드·설치하고 대상 Simulator를 선택한다.

```sh
npm exec --yes --package=node@22.23.2 -- npm run ios -- --device
```

Metro 터미널을 유지한 상태에서 아래 파일을 수정한다.

| 바꾸려는 부분 | 파일 |
|---|---|
| 발매 일정 목록·카드 배치 | `apps/mobile/src/app/(tabs)/index.tsx` |
| 하단 탭·메뉴 | `apps/mobile/src/app/(tabs)/_layout.tsx` |
| 설정 화면 | `apps/mobile/src/app/(tabs)/settings.tsx` |
| 일정 상세 | `apps/mobile/src/app/releases/[id].tsx` |
| 공통 글꼴·색상·이미지·간격 | `apps/mobile/theme.ts` |
| 커버 표시 | `apps/mobile/src/components/record-art.tsx` |

예를 들어 카드의 padding, 제목 fontSize, 항목 사이 gap을 하나씩 바꾸고 저장해 비교한다. 반영되지 않으면 Metro에서 `r`을 눌러 다시 로드한다. native 모듈·config plugin 변경은 앱을 재빌드해야 한다. `.env.local` 변경은 Metro를 재시작한다.

Simulator의 개발 메뉴에서 Fast Refresh 상태와 요소 검사를 확인할 수 있다. 작은 기기와 큰 기기에서 탭·긴 제목·스크롤을 비교하고, 다크 모드와 큰 글자도 확인한다. Simulator별 설치는 한 번 필요하다. TestFlight와 Release 앱은 이 실시간 편집 흐름을 위한 빌드가 아니다.

이 앱은 실제 Funnel API를 조회한다. Metro는 UI 코드를 제공하고 Mac mini의 Docker/Funnel은 일정 데이터를 제공하므로 둘의 연결 오류를 구분한다. 웹 PWA는 React Native 앱과 별도 화면이다.

## 웹: 별도 localhost 개발 화면

실제 공개 사이트는 production 빌드이므로 파일 저장만으로 바뀌지 않는다. 기존 3000 포트를 유지하면서 3001에 개발 웹을 띄우면 편집 결과를 빠르게 볼 수 있다.

```sh
cd /Users/jaehyeon/PersonalProjects/OROT/apps/web
API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3001
```

브라우저에서 `http://127.0.0.1:3001`을 연다. 피드는 `app/page.tsx`, 상세는 `app/releases/[id]/page.tsx`, 공통 스타일은 `app/globals.css`에서 수정한다. 개발자 도구의 기기 화면 모드로 폭을 바꾸어 확인할 수 있다. 개발자 도구에서 직접 바꾼 CSS는 임시이므로 최종 변경은 소스 파일에 반영한다.

3001은 개발 확인용이며 Funnel 대상을 바꾸지 않는다. UI 확인 중 알림 구독 버튼을 누르면 실제 API를 사용할 수 있으므로 화면 편집과 실제 구독·발송 검증을 구분한다. 완료한 웹 변경은 lint·테스트·build 후 production 웹 이미지를 재빌드·교체해야 공개 사이트에 반영된다.

## 운영자 화면

운영자 화면은 Next.js가 아니라 `apps/api/src/orot_api/routers/admin_ui.py`의 HTML/CSS/JavaScript다. Mac의 브라우저에서 `http://127.0.0.1:8000/admin`으로 접속한다. 기존 운영자 키로 로그인한다.

API 컨테이너는 소스 변경을 리로드하므로 코드 저장 후 브라우저를 새로고침한다. React Fast Refresh처럼 이미 열린 폼이 자동 갱신되지는 않는다. 저장하지 않은 입력이 있다면 새로고침 전에 주의한다. 단순 스타일 확인에는 실제 일정 등록이나 공개가 필요하지 않다.

## 피드백을 주고받는 방법

스크린샷이나 화면을 함께 보며 “하단 탭 높이 줄이기”, “음반 카드 사이 간격 16으로”, “제목 두 줄까지 표시”처럼 위치·변경·기대 모습을 지정하면 코드에 반영한 뒤 같은 화면에서 확인하기 쉽다. 버튼 배치와 텍스트부터 조정하고, 화면 전체 디자인을 결정한 뒤 애니메이션을 추가하는 순서가 효율적이다.

테마의 자세한 편집 방법은 [모바일 테마 안내](../apps/mobile/THEME.md)를 따릅니다.
