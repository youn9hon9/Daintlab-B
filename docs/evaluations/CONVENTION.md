# 후보 브랜치 버전·커밋 컨벤션

## 브랜치 역할

| 브랜치 | 목표 | 트랙 | 버전 접두사 |
|---|---|---|---|
| `yh-submission` | 벤치마크상 | `benchmark` | `B` |
| `yh-submission2` | 프론티어상 | `frontier` | `F` |

두 브랜치는 서로 다른 목표를 최적화한다. 모델을 직접 병합하거나 버전 번호를 공유하지
않는다. 공통 문서나 평가 도구는 `dev`에서 관리한다.

## 커밋 메시지

후보 브랜치의 모든 새 커밋은 다음 형식만 사용한다.

```text
<type>(<track>/<version>): <summary>
```

허용하는 `type`은 `feat`, `fix`, `perf`, `refactor`, `test`, `docs`, `chore`다.
버전은 세 자리 숫자로 기록한다.

```text
perf(benchmark/B001): retrieval 지연 축소
fix(benchmark/B002): upstream timeout 복구 경로 수정
feat(frontier/F001): 다중 근거 합성 전략 추가
docs(frontier/F001): F001 설계 근거 보강
```

잘못된 예시는 다음과 같다.

```text
Update model
feat: B001 개선
perf(yh-submission/B001): 지연 축소
feat(frontier/Y4): 새 전략
```

## 버전 증가 규칙

- prompt, 모델 경로, retrieval, timeout, dependency 또는 런타임 설정처럼 평가 결과에
  영향을 줄 수 있는 변경에는 새 버전을 부여한다.
- `docs`, `test`, 동작에 영향을 주지 않는 `chore`는 현재 버전을 유지할 수 있다.
- 한 번 평가한 버전의 모델 동작을 바꾼 뒤 같은 버전을 재사용하지 않는다.
- 평가 결과의 정체성은 브랜치 이름, 버전과 40자리 SHA 세 값으로 기록한다.

## 평가 명령

평가 노트북에서는 버전을 직접 입력하지 않는다. 최신 커밋 메시지가 버전의 정본이다.

```powershell
.\proxy yh-submission
.\proxy yh-submission2
```

스크립트는 원격 최신 커밋을 가져와 컨벤션을 검사하고 `B001` 또는 `F001`을 자동으로
결과 이름에 사용한다. 최신 커밋이 규칙에 맞지 않으면 평가를 시작하지 않는다.

동시에 평가하려면 터미널을 하나씩 열어 각 명령을 실행한다. 포트와 Lunit API 키는
프로세스마다 자동 배정된다.
