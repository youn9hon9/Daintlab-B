# 국가법령정보센터(law.go.kr) Open API 실무

`openapi_law_search` · `openapi_law_list_articles` · `openapi_law_get_article` 3개 MCP tool이 감싸는 법제처 "국가법령정보 공동활용" Open API의 실제 호출 구조, 법령 종류 구분, 시행일 버전 관리, 조문 인용 표기 규칙을 조사한 자료.

## API 실제 구조: 검색 → MST → 조문 목록 → 조문 본문

법제처 Open API는 크게 **목록조회**와 **본문조회** 두 종류로 나뉜다. 인증에는 `OC`(발급받은 API 인증키, 보통 가입 이메일 ID 형태) 파라미터가 필요하다.

| 단계 | 대응 MCP tool | 실제 endpoint (target) | 핵심 파라미터 | 반환값 |
|---|---|---|---|---|
| 1. 법령 검색 | `openapi_law_search` | `GET https://www.law.go.kr/DRF/lawSearch.do?target=law` (행정규칙은 `target=admrul`, 자치법규는 `target=ordin`) | `OC`, `query`(법령명 키워드), `type` | 검색 결과 목록 + **법령일련번호(MST)** + 법령상세링크 |
| 2. 조문 목록 조회 | `openapi_law_list_articles` | `GET https://www.law.go.kr/DRF/lawService.do?target=law` (또는 `eflaw`=시행일 기준 현행법령) | `OC`, `MST` 또는 `ID`, `efYd`(시행일자, 정수 YYYYMMDD) | 법령 기본정보 + 조문 전체 목록(조문번호·조문제목·조문시행일) |
| 3. 조문 본문 조회 | `openapi_law_get_article` | `GET https://www.law.go.kr/DRF/lawService.do?target=lawjosub` | `OC`, `ID` 또는 `MST`, `JO`(조번호 6자리), `HANG`(항 6자리), `HO`(호 6자리), `MOK`(목 문자) | 선택 조/항/호/목의 전문, 조문시행일자, 제개정 유형 |

확인된 실제 요청 예시(검색 결과에서 그대로 확인됨):
```
https://www.law.go.kr/DRF/lawSearch.do?OC=test&target=eflaw&query=자동차관리법
https://law.go.kr/DRF/lawService.do?OC=ducut91&target=law&MST=269797&type=XML&efYd=20250701
http://www.law.go.kr/DRF/lawService.do?OC=test&target=lawjosub&type=XML&ID=001823&JO=000300&HANG=000100&HO=000200&MOK=다
```

**MST(법령마스터번호, `lsi_seq`)**는 law.go.kr 웹 UI의 `lsiSeq` 파라미터와 동일 개념으로, 검색 API 응답에서만 얻을 수 있는 "이후 조회를 위한 handle" 역할을 한다. 즉 harness는 반드시 `openapi_law_search`로 먼저 MST를 획득한 뒤에만 `openapi_law_list_articles`·`openapi_law_get_article`을 호출할 수 있는 구조다.

`JO`(조번호) 필드는 실제 URL 관찰상(`joNo=024500` 형태) **앞 4자리가 조번호, 뒤 2자리가 "~조의N" 가지번호**인 것으로 보인다(예: 제41조의4 → `004104`). 다만 이 필드 인코딩 규칙이 공식 가이드 문서에 명문화된 것은 확인하지 못했다 — **정확한 출처 미확인, 추가 검증 필요**.

## 법률 · 행정규칙 · 자치법규의 차이와 의료 도메인 관련성

`openapi_law_search`의 설명대로 이 tool은 세 카테고리(법률/행정규칙/자치법규)를 검색 대상으로 포괄한다. law.go.kr은 이를 아래처럼 구분해 별도 API 계열로 제공한다.

| 구분 | 제정 주체 | law.go.kr 분류 | 대회 의료 도메인 관련성 |
|---|---|---|---|
| **법률(및 시행령·시행규칙)** | 국회(법률) / 대통령령·총리령·부령(하위 명령) — law.go.kr에서는 이들을 통틀어 "현행법령" 카테고리로 검색 | `target=law`/`eflaw` | 국민건강보험법, 의료법, 약사법 등 기본법과 그 시행령·시행규칙(부령) — **급여기준의 법적 근거(위임 조항)가 위치하는 최상위 계층** |
| **행정규칙** | 중앙행정기관의 훈령·예규·**고시**·지침 | `target=admrul` | 보건복지부 고시(예: 요양급여의 적용기준 및 방법에 관한 세부사항) — 법령의 위임을 받아 구체적 급여기준·상한액·인정기준을 정하는 "법령보충적 행정규칙"으로 대외적 구속력을 가짐 |
| **자치법규** | 지방자치단체(조례·규칙) | `target=ordin` | 건강보험은 전국 단일 제도이므로 이 대회 맥락에서는 관련성이 낮음 |

**실제로 확인한 위임 체계 예시** (건강보험 급여기준의 전형적인 3단 구조):

1. **국민건강보험법**(법률) 제41조제3항: "요양급여의 방법·절차·범위·상한 등의 기준은 보건복지부령으로 정한다"
2. **국민건강보험 요양급여의 기준에 관한 규칙**(보건복지부령, law.go.kr 분류상 "법령"/법률 카테고리 — 2026.1.26. 시행 보건복지부령 제1154호까지 개정 확인)
3. **요양급여의 적용기준 및 방법에 관한 세부사항**(보건복지부고시, law.go.kr 분류상 "행정규칙" — 2026.4.1. 시행 보건복지부고시 제2026-78호까지 개정 확인)

이 3단 체계는 `09_국내_건강보험법률RAG_사례.md`에서 언급한 HIRA 급여기준 고시(`hira_updates_search` tool이 다루는 영역)와 **정확히 같은 대상**이다. 즉 `openapi_law_*` 3개 tool은 이 체계의 1~2단(법률·부령)을, `hira_updates_search`는 3단(고시)과 그 개정/공개 심의사례를 담당하는 상호 보완 관계로 이해하는 것이 실무적으로 정확하다.

## 시행일(efYd)과 조문 버전 관리

- `lawService.do?target=eflaw`는 `efYd`(YYYYMMDD 정수) 파라미터로 **특정 시행일자 기준의 조문 버전**을 지정 조회하도록 설계되어 있다. 이는 개정 이력이 있는 법령에서 "현재 시행 중인 버전"과 "향후 시행 예정 버전"이 공존할 때 필수적이다.
- law.go.kr은 "현행법령(시행일 기준)"과 "법령(공포일 기준)" 두 계열의 API를 별도로 제공한다 — 공포되었지만 아직 시행되지 않은 개정과, 이미 시행 중인 조문을 혼동하지 않으려면 어느 계열을 호출하는지 명확히 구분해야 한다.
- MST(법령일련번호)가 법령의 **개정 시행일자 버전마다 별도로 부여되는지, 하나의 법령에 고정되는지**는 공식 문서에서 명시적으로 확인하지 못했다. 검색 API 응답이나 웹 UI에서 서로 다른 `lsiSeq` 값이 다수 관측되는 점으로 미루어 버전별로 별도 MST가 존재할 가능성이 높다 — **정확한 출처 미확인, 추가 검증 필요**. 실무적으로는 매 조회 시 `openapi_law_search`로 최신 MST를 재확인하고, 응답에 포함된 시행일자를 그대로 신뢰하는 것이 안전하다.
- **혼동 방지 원칙**: (1) 조문 조회 결과에 포함된 시행일자를 항상 답변에 노출한다. (2) 사용자가 특정 시점을 언급하지 않으면 "오늘 날짜 기준 현행"으로 명시적으로 `efYd`를 지정해 호출한다. (3) 여러 버전이 후보로 잡히면 가장 최근 시행일자이면서 오늘 날짜를 넘지 않는 버전을 우선한다.

## 조문 인용(citation) 표기 규칙과 환각 방지

- 한국 법령의 조문 위계는 **편 > 장 > 절 > 관 > 조 > 항 > 호 > 목** 순이다.
- 정식 인용 표기는 "{법령명} 제○조제○항제○호○목" 형식이며, 전통적으로는 붙여쓰기가 원칙이었으나("제41조제1항제2호가목") 최근에는 가독성을 위해 띄어쓰기도 통용된다("제41조 제1항 제2호 가목"). 법령명은 정식명칭 또는 법제처가 공인한 약칭을 쓰되 '시행령'·'시행규칙'·'특례법' 등 성격을 나타내는 단어는 띄어 쓰는 것이 원칙이다.
- **환각(hallucination) 방지 원칙**:
  1. L2가 조문 번호·내용을 기억(parametric memory)에서 생성하지 않고, 반드시 `openapi_law_get_article` 호출 결과의 원문 텍스트를 그대로 인용하도록 강제한다. Retrieval 단계 system prompt에서 "법령 조문은 절대 암기된 내용으로 답하지 말고 tool 호출로 확인하라"를 명시할 필요가 있다.
  2. `openapi_law_get_article` 응답에 포함되는 **조문 시행일과 law.go.kr link**를 Generation 단계 citation에 그대로 노출해, 사용자가 원문을 직접 검증할 수 있게 한다(L2 안내 문서의 `cite_uid` → 최종 답변 각주 매핑 방식과 동일한 패턴).
  3. 조/항/호 번호를 답변에서 재구성할 때, tool 응답 필드(조문번호·항번호·호번호)를 그대로 조합해서 표기하고 임의로 요약·재번호하지 않는다.
  4. 상위 조항 인용 시 `04_법령가이드라인_구조화청킹.md`의 parent-document retrieval 원칙과 결합 — 특정 항만 조회했더라도 그 항이 속한 조 전체 맥락(예: 제41조제3항을 인용할 때 제41조제1항의 "요양급여" 정의)을 함께 확인해야 오독을 막을 수 있다.

## 의료 AI 챗봇이 참조할 후보 법령 목록

| 법령명 | 종류 | 급여기준(이 대회 핵심 맥락) 관련도 | 비고 |
|---|---|---|---|
| **국민건강보험법** | 법률 | ★★★★★ 최우선 | 요양급여·급여 제한·본인부담 등 급여기준 전체의 법적 근거. 제41조(요양급여) 확인 완료 |
| **국민건강보험 요양급여의 기준에 관한 규칙** | 법률(보건복지부령) | ★★★★★ 최우선 | 국민건강보험법 제41조제3항·제4항의 위임을 받아 급여기준의 방법·절차·범위·상한을 직접 규정 |
| 의료법 | 법률 | ★★★☆☆ | 의료인 자격·의료기관 개설·진료기록 등 — 급여기준 자체보다는 "적법한 진료 주체" 판단에 관련 |
| 약사법 | 법률 | ★★★☆☆ | 의약품 제조·판매·조제 규율 — 약가·처방 관련 질의에서 국민건강보험법과 함께 참조될 가능성 |
| 마약류 관리에 관한 법률 | 법률 | ★★☆☆☆ | 마약류 처방·관리 규율 — 특정 약물(마약성 진통제 등) 질의에서만 관련 |
| 응급의료에 관한 법률 | 법률 | ★★☆☆☆ | 응급의료체계·응급실 이송 규율 — 급여기준보다는 응급 상황 대응 절차 질의에 관련 |

**우선순위 판단 근거**: [MCP tools 문서](../competition/mcp-tools.md)와 `09_국내_건강보험법률RAG_사례.md`가 명시하는 "건강보험 관련 법률" 소스, 그리고 `hira_updates_search`가 다루는 HIRA 급여기준 고시가 모두 국민건강보험법 제41조 위임 체계와 직결된다. 반면 의료법·약사법·마약류관리법·응급의료법은 진료행위·처방의 적법성 판단에는 필요하지만 "급여기준" 자체의 법적 근거는 아니므로 상대적으로 후순위로 판단된다. 이 우선순위 자체는 본 조사자의 종합 판단이며, 대회 스펙이나 실제 평가 질문 분포로 재검증이 필요하다.

## 대회 도구 매핑

L2의 2단계 구조(Retrieval → Generation, [L2 문서](../competition/l2.md) 참고)에서 3개 law.go.kr tool은 Retrieval 단계에서 아래 순서로 호출되는 것을 전제로 설계된 것으로 보인다.

1. **`openapi_law_search`**: 사용자 질문에서 언급되거나 유추되는 법령명(예: "국민건강보험법", 또는 급여기준 관련 질문이면 "국민건강보험 요양급여의 기준에 관한 규칙")으로 검색해 후보 법령과 **MST**를 확보한다. 법령명이 불명확하면 키워드(예: "요양급여 인정기준")로 먼저 검색해 후보를 좁힌다.
2. **`openapi_law_list_articles`**: 확보한 MST로 해당 법령의 조문 목록을 나열하고, 조문 제목 filter(예: "요양급여")로 질문과 관련된 조문을 좁혀 **stable article key**를 얻는다. 이 단계에서 여러 후보 조문이 잡히면 제목만으로 판단하지 말고 다음 단계에서 본문을 비교한다.
3. **`openapi_law_get_article`**: 좁힌 article key로 조문 전문을 조회해 citation 가능한 원문·시행일·law.go.kr link를 확보한다. `finalize_retrieval`에 넘길 `cite_uid`는 이 호출 결과에서 나오는 것으로 간주해야 한다.

**호출 전략상 유의점**:
- 법령명이 확실치 않은 질문(예: "요양급여 상한선 근거가 뭐야?")은 1→2→3을 모두 거쳐야 하지만, 조문 번호까지 명시된 질문(예: "국민건강보험법 제41조제3항 내용 알려줘")은 `openapi_law_search`로 MST만 얻고 바로 `openapi_law_get_article`로 건너뛸 수 있어 tool call 예산을 절약할 수 있다(L2 가이드의 "Retrieval 중 tool call 횟수를 제한하세요" 원칙과 부합).
- 급여기준 질문은 법률(국민건강보험법·부령)과 행정규칙(보건복지부 고시)이 함께 필요한 경우가 많으므로, `openapi_law_*` 3종과 `hira_updates_search`를 같은 Retrieval turn 안에서 병행 호출하는 라우팅 설계가 필요하다(`08_쿼리라우팅_멀티에이전트RAG.md` 참고).
- 시행일 혼동 방지를 위해, `openapi_law_list_articles`/`openapi_law_get_article` 호출 시 가능하면 오늘 날짜(또는 질문이 특정하는 시점)를 기준 시행일로 명시하고, 응답의 시행일자를 그대로 최종 답변에 실어 사용자가 버전을 검증할 수 있게 한다.

## 전략적 시사점

- `openapi_law_search`가 MST를 반환하는 구조이므로, harness는 이 tool을 반드시 첫 호출로 강제하는 게 안전하다 — MST 없이는 나머지 두 tool이 무의미하다.
- 법률(국민건강보험법·요양급여기준 규칙)과 행정규칙(보건복지부 고시)이 하나의 위임 체계로 연결되어 있다는 점은, `openapi_law_*`와 `hira_updates_search`를 별개 소스로 취급하지 말고 "상위 법적 근거 + 하위 세부 기준"을 짝지어 인용하는 답변 템플릿을 만들 근거가 된다.
- 시행일(efYd)·MST 버전 관리의 세부 규칙은 공식 문서만으로 완전히 확인되지 않았다 — 실제 하네스 구축 시 동일 법령을 여러 시행일로 조회해 MST 값이 바뀌는지 직접 테스트해보는 것이 가장 확실한 검증 방법이다.
- 조문 인용 표기(제○조제○항제○호)는 법조문 그대로 tool 응답 필드를 조합해 재현하고, 요약·재구성하지 않는 것이 hallucination 방지의 핵심이다 — `04_법령가이드라인_구조화청킹.md`의 구조 보존 원칙과 정확히 같은 방향이다.
- 자치법규(`target=ordin`)는 이 대회의 전국 단일 건강보험 제도 맥락에서 사실상 호출 우선순위가 낮다 — tool 예산이 제한적이라면 법률·행정규칙 조회를 우선하고 자치법규는 지역 특이적 질문에서만 고려.

## 출처
- [OPEN API 활용가이드 - 국가법령정보 공동활용](https://open.law.go.kr/LSO/openApi/guideList.do)
- [OPEN API 활용방법 - 국가법령정보 공동활용](https://open.law.go.kr/LSO/openApi/openApiManual.do)
- [현행법령(공포일) 본문 조항호목 조회 API](https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsNwJoListGuide)
- [법령 시행일자 현황 API 안내](https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsEfYdInfoGuide)
- [자치법규 목록 조회 API](https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=ordinListGuide)
- [행정규칙 목록 조회 API](https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=admrulListGuide)
- [법제처 국가법령정보 공유서비스 - 공공데이터포털](https://www.data.go.kr/data/15000115/openapi.do)
- [중앙부처 1차 해석: 법·시행령·시행규칙·행정규칙 간의 차이점 - 국가법령정보센터](https://www.law.go.kr/LSW/cgmExpcInfoP.do?cgmExpcDatSeq=427740&mode=2&ofiClsCd=350122)
- [법령의 종류 - 어린이 법제처](https://www.moleg.go.kr/menu.es?mid=a20503010000)
- [법률문헌 등의 인용방법 표준안 - 법원도서관](https://jpri.scourt.go.kr/fileDownLoad.do?seq=329)
- [법 조문 체계 - 나무위키](https://namu.wiki/w/%EB%B2%95%20%EC%A1%B0%EB%AC%B8%20%EC%B2%B4%EA%B3%84)
- [국민건강보험 요양급여의 기준에 관한 규칙 - 국가법령정보센터](https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=183815)
- [요양급여의 적용기준 및 방법에 관한 세부사항(보험급여) - 국가법령정보센터 행정규칙](https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000276678)
- [국민건강보험법 - 국가법령정보센터](https://www.law.go.kr/LSW//lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000622785&lsId=001971&print=print)
- [법제처 Open API 인증키 발급 가이드 - jurisupport](https://github.com/jurisupport/jurisupport-plugins/blob/main/guides/07_law_openapi_key.md)
