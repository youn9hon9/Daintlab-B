# 의약품 허가·안전성: DailyMed·MFDS·FAERS 실무

의약품 허가정보·라벨·이상반응(안전성) 도메인은 미국(DailyMed, FAERS)과 한국(MFDS) 두 개의 서로 다른 규제 체계 데이터를 함께 다뤄야 하는 영역. 두 나라의 허가 상태·적응증이 다를 수 있고, FAERS는 "인과관계가 증명된 부작용 통계"가 아니라 "자발적으로 접수된 의심 사례"라는 점에서, 챗봇이 원문 그대로를 과잉 해석해 사용자에게 전달하면 위험한 오답이 나올 수 있는 영역이기도 함.

## 1. DailyMed Drug Label 구조 (SPL)

DailyMed가 배포하는 처방정보(Prescribing Information)는 FDA가 요구하는 XML 기반 표준 포맷인 **SPL(Structured Product Labeling, HL7 표준)**로 작성된다. SPL 문서는 76개의 표준 section heading으로 나뉘고, 각 section은 **LOINC 코드**로 식별된다. `adr_retrieve_drug_info`가 "주요 section"을 반환한다고 했을 때, 실제로는 이 LOINC 코드로 구분된 section들 중 안전성 관련 항목을 골라오는 것으로 추정할 수 있다.

확인된 주요 section과 LOINC 코드:

| Section (영문) | LOINC 코드 | 내용 |
|---|---|---|
| Boxed Warning | 34066-1 | 치명적·생명위협적·영구장애를 유발할 수 있는 가장 심각한 경고 (박스형으로 강조) |
| Indications and Usage | 34067-9 | 승인된 적응증 |
| Dosage and Administration | 34068-7 | 용법·용량 |
| Contraindications | 34070-3 | 절대 금기 (예: SOLIRIS는 미해결 수막구균 감염 환자에 금기) |
| Warnings | 34071-1 | 경고 (Warnings and Precautions 도입 이전 구형 포맷에서 사용되던 섹션) |
| Warnings and Precautions | 43685-7 | 심각하거나 임상적으로 유의한 이상반응 (Boxed Warning만큼 심각하지는 않지만 주의가 필요한 항목) |
| Drug Interactions | 34073-7 | 병용 약물·음식과의 상호작용 |
| Adverse Reactions | 34084-4 | 임상시험·시판 후 조사에서 관찰된 이상반응 목록 (빈도별로 구분되는 경우가 많음) |

Boxed Warning과 Warnings and Precautions의 차이: **Boxed Warning은 잠재적 이익 대비 치명적·생명위협적·영구장애 수준의 심각한 이상반응**에만 부여되고, **Warnings and Precautions는 심각하거나 임상적으로 유의미하지만 박스경고 수준은 아닌 이상반응**을 다룬다. 챗봇이 "이 약의 경고사항"을 물어보는 질의에 답할 때 이 위계를 구분해 전달하는 것이 안전하다 (Boxed Warning을 일반 Warning과 동급으로 뭉뚱그리면 위험도를 과소평가하게 됨).

DailyMed는 REST API(`/spls` 등)로 `drug_name`(generic/brand 선택 가능), `rxcui`, `ndc`, `unii`, 제조사명 등으로 검색할 수 있고 SPL 전체를 XML/JSON으로 반환한다. 다만 실제 API 응답 필드의 세부 구조(예: section별로 구조화되어 오는지, 원문 XML을 그대로 파싱해야 하는지)는 `/spls` 목록 endpoint 문서에서는 확인되지 않았다 — **정확한 응답 스키마는 `adr_retrieve_drug_info` 실제 호출 결과로 추가 검증 필요.**

## 2. 한국 MFDS 의약품 허가정보 체계

### 허가 vs 취하(취소)의 차이

- **허가(유효 허가)**: 식약처가 안전성·유효성 심사를 거쳐 의약품 제조·판매를 승인한 상태. 허가일자·허가번호가 부여된다.
- **취하**: 제약사가 스스로 허가를 반납(자진 취하)하거나 식약처가 허가를 취소한 상태. 취하된 제품은 더 이상 유통·처방될 수 없지만, 데이터베이스에는 "과거에 허가받았던 이력"으로 남는 경우가 많다.
- 공공데이터포털의 "의약품 제품 허가정보" OpenAPI는 실시간 데이터 기준이며, **인허가 절차 진행 중이거나 폐기·취소·취하된 데이터는 포함되지 않는 경우가 있다**는 안내가 있다 — 즉 이 API만으로 "취하 여부"를 100% 판단하기 어려울 수 있으므로, `openapi_mfds_check_drug_permission`이 "유효 허가와 취하 허가를 구분한다"고 명시한 것은 별도 필드(허가상태 코드 등)를 통해 이를 보정한 것으로 추정된다. **정확한 응답 필드명(허가상태, 취하일자 등)은 Swagger 명세 원문 확인이 필요 — 추가 검증 필요.**

### 실제 조회 경로

- **의약품안전나라(nedrug.mfds.go.kr)**: MFDS가 운영하는 통합 의약품 정보 시스템. 제품명·성분명·업체명·품목기준코드·제형 등으로 검색해 허가정보, 안전사용정보, 특허정보, 생동성시험정보, 임상시험정보를 한 번에 조회할 수 있다.
- **e약은요 서비스**: 의약품안전나라 내 서비스로, 공급 이력이 있는 일반의약품 위주로 업체명·제품명·품목기준코드·효능효과·용법용량·주의사항·상호작용·부작용·저장방법을 요약 제공한다.
- **공공데이터포털(data.go.kr) / 식의약데이터포털(data.mfds.go.kr)**: 동일 데이터를 OpenAPI(XML/JSON)로 제공. 원칙적으로 무료.

### ATC 코드

ATC(Anatomical Therapeutic Chemical Classification, 해부학적 치료화학 분류체계)는 WHO 산하 WHOCC(Collaborating Centre for Drug Statistics Methodology)가 관리하는 국제 표준 의약품 분류 코드. 1976년 최초 발표. 5단계 7자리(문자+숫자)로 구성되며, 약물이 작용하는 신체 계통·치료군·약리학적 특성·화학적 특성까지 계층적으로 표현한다. 하나의 약물이 작용 부위에 따라 여러 ATC 코드를 가질 수도 있다. 한국 HIRA도 별도로 "의약품 ATC 코드" 목록을 분기별로 공개하고 있어, `openapi_mfds_get_drug_indication`이 반환하는 ATC data는 국내 급여기준(HIRA) 문서나 해외 문헌에서 동일 치료군 약물을 교차 검색하는 연결고리로 활용할 수 있다.

## 3. 동일 성분(active ingredient) 대체 시 실무 주의점

가장 널리 알려진 사례가 **피나스테리드(finasteride)**: 동일 성분이지만 **용량에 따라 적응증 자체가 다르게 허가**되어 있다.

| 제품명 | 용량 | 허가 적응증 |
|---|---|---|
| 프로스카(Proscar) | 5mg | 전립선비대증(BPH) |
| 프로페시아(Propecia) | 1mg | 남성형 탈모 |

즉 "같은 성분이니 대체 가능하다"고 단순 판단하면 안 되고, **용량·허가 적응증·투여 대상(성별, 연령 등)이 일치하는지**를 반드시 함께 확인해야 한다. 실제로 국내에서는 저가의 프로스카(5mg)를 탈모 치료 목적으로 분할 처방하는 "편법 처방" 관행이 있어 언론에서 지속적으로 지적된 바 있다.

이를 대회 harness에 적용하면: `openapi_mfds_find_drugs_by_ingredient`로 동일 성분의 다른 제품을 찾았더라도, 곧바로 "대체 가능"이라고 답하지 말고 **① 각 제품의 허가 상태(유효/취하)를 `openapi_mfds_check_drug_permission`으로 재확인, ② 각 제품의 적응증·용량을 `openapi_mfds_get_drug_indication`으로 비교**하는 2단계 검증을 거치는 것이 안전하다.

## 4. FAERS 데이터의 구조적 한계와 안전한 답변 원칙

### 구조적 한계

- **자발적 보고(spontaneous report) 시스템**: FAERS는 제약사의 의무 보고와 의료인·환자·소비자의 자발적(MedWatch) 보고로 구성된다. 보고서에 특정 약물과 이상반응이 함께 기재되어 있다는 사실은 **"의심되는 연관성"을 뜻할 뿐, 확정된 인과관계를 의미하지 않는다.**
- **분모(exposure) 정보 부재**: FAERS는 그 약을 실제로 복용한 환자 수(분모)를 포함하지 않는다. 따라서 보고 건수만으로 "발생률"이나 "위험도"를 계산할 수 없다.
- **비교군 부재**: 비노출군 대비 발생 배경율(background incidence)을 알 수 없어, 보고된 이상반응이 약물 때문인지 자연 발생인지 구분하기 어렵다.
- **보고 편향**: 중대하거나 새로운(novel) 이상반응일수록 더 많이 보고되는 경향이 있고, 언론 보도 등으로 특정 이상반응에 대한 "주목 효과(notoriety effect)"가 생기면 실제 위해도 변화 없이 보고 건수만 급증할 수 있다.
- **중복 보고**: 동일 사례가 의료진·제약사·환자 등 여러 경로로 중복 제출되는 경우가 알려진 문제로 지적된다.
- **약물명 비정형 입력**: 보고자가 상품명/성분명/오타 등을 혼용해 입력하는 경우가 많아 약물 식별 자체가 불완전할 수 있다.

### 신호탐지(Disproportionality Analysis) 지표: PRR / ROR

FAERS 원시 보고 건수 대신 신호의 유의성을 가늠하기 위해 약물감시(pharmacovigilance) 분야에서 쓰는 2×2 분할표 기반 지표:

- **PRR(Proportional Reporting Ratio)**: 특정 약물에서 특정 이상반응이 보고된 비율을, 전체 데이터베이스(다른 모든 약물)에서 같은 이상반응이 보고된 비율과 비교.
- **ROR(Reporting Odds Ratio)**: PRR과 유사하되 오즈비(odds ratio) 형태로 계산 — 상대위험도 추정에 더 가깝고, 대조군 선정에 관한 편향을 통제하기 유리하다는 방법론적 이점이 있어 PRR보다 선호되는 경향이 있다.
- 두 지표 모두 **"신호(signal)"를 찾아 추가 조사가 필요한 후보를 좁히는 가설 생성(hypothesis-generating) 도구**이지, 그 자체로 인과관계를 확정하는 지표가 아니다.

`faers_12q4_25q4`는 `rag_sql_query`로 구조화 SQL 조회가 가능한 데이터셋이지만, MCP tool 자체가 PRR/ROR을 자동 계산해주지는 않을 가능성이 높다 — 단순 COUNT 집계 결과를 신호탐지 지표처럼 제시하지 않도록 주의해야 한다.

### "이 약 때문에 부작용이 몇 건 보고됐나요?" 같은 질문에 답할 때 반드시 포함할 caveat

1. **보고 건수 ≠ 발생률**: FAERS는 분모(노출 환자 수)가 없으므로 "몇 명 중 몇 명"이라는 형태로 위험도를 제시할 수 없다.
2. **인과관계 미확정**: 보고서에 약물-이상반응이 함께 기재되었다는 것은 "의심 사례"이지 "확인된 부작용"이 아니다.
3. **중복·편향 가능성**: 동일 사례 중복 제출, 언론 보도 등에 따른 보고 쏠림이 있을 수 있어 건수 자체가 실제 위해도를 비례해서 반영하지 않는다.
4. **비교 시 신호탐지 지표 필요**: 단순 건수 비교보다 PRR/ROR 등 disproportionality 지표가 필요하며, SQL 단순 COUNT 결과를 신호로 오인하면 안 된다.
5. **공식 라벨과의 병행 확인 권고**: FAERS 신호는 DailyMed의 공식 라벨(Adverse Reactions section, LOINC 34084-4)에 이미 반영되어 있는 알려진 이상반응인지, 아직 라벨에 없는 새로운 신호인지 구분해 안내하는 것이 안전하다.

## 5. 미국(DailyMed/FAERS) vs 한국(MFDS) 데이터 상충 시 원칙

- **허가 상태가 다른 경우** (미국 승인·한국 미허가 등): 규제기관마다 심사 기준(임상적 유의성 판단, 대리 결과지표 인정 여부 등)이 달라 같은 약물이라도 결론이 다를 수 있다. 실제 사례로, 미국 FDA가 재생의료 첨단치료제(RMAT)·혁신치료제(BT)로 지정한 국내 개발 줄기세포치료제 '조인트스템'이 국내 식약처에서는 품목허가가 반려된 채 장기간 계류된 사례가 보도된 바 있다 (다만 이는 "FDA 정식 승인 vs 한국 미허가"가 아니라 "FDA 개발 촉진 지정 vs 한국 허가 반려"이므로 지정과 승인을 혼동하지 않아야 한다). **원칙: 미국에서 승인/지정되었다는 사실만으로 한국에서도 안전하거나 곧 허가될 것이라고 단정해 답변하면 안 되며, 반드시 한국 허가 상태(`openapi_mfds_check_drug_permission`)를 별도로 확인해 명시해야 한다.**
- **적응증이 다른 경우**: 동일 성분이라도 국가별로 승인된 적응증·용량이 다를 수 있다 (위 피나스테리드 사례 참고). 미국 라벨(DailyMed)의 적응증을 그대로 한국 상황에 적용해 답하면 오답이 될 수 있으므로, 한국 사용자 대상 질의에는 **`openapi_mfds_get_drug_indication`의 국내 허가 적응증을 우선 원칙(source of truth)으로 삼고**, DailyMed/FAERS 정보는 "미국에서는 이렇게 승인·보고되어 있다"는 참고 정보로 명확히 구분해 인용해야 한다.
- **정보가 상충하는 경우**: 두 출처를 병기하되 어느 국가 기준인지 라벨링하고("미국 FDA 라벨 기준 / 한국 식약처 허가사항 기준"), 임의로 하나를 정답처럼 종합하지 않는다. 국내 첨부문서(라벨) 작성 가이드라인 자체가 미국·유럽보다 구체성이 낮고 환자용 문서가 별도로 없는 경우가 많다는 지적도 있어, 한국 자료가 상대적으로 소략할 때는 그 사실 자체를 답변에 명시하는 것이 안전하다.

## 대회 도구 매핑

| 조사 내용 | 관련 MCP tool | 호출 전략 |
|---|---|---|
| DailyMed SPL section 구조 (Boxed Warning/Warnings and Precautions/Adverse Reactions/Drug Interactions/Contraindications) | `adr_retrieve_drug_info` | brand name 또는 INN(영문)으로 조회하되, 응답에서 Boxed Warning과 일반 Warnings/Warnings and Precautions를 구분해 심각도 위계를 살려 요약. 국문 질의는 영문 성분명/제품명으로 변환 후 호출 필요 |
| MFDS 허가 vs 취하 구분 | `openapi_mfds_check_drug_permission` | 부분 product name 검색 결과에서 "유효 허가"와 "취하"를 명확히 구분해 답변에 상태를 명시. 취하된 제품을 유효 허가로 오인해 안내하지 않도록 최종 답변 전 상태 재확인 |
| 동일 성분 대체 candidate 탐색 | `openapi_mfds_find_drugs_by_ingredient` | 성분명으로 대체 후보를 찾은 뒤, 곧바로 대체 가능하다고 답하지 말고 아래 두 tool로 적응증·허가 상태를 교차 검증 |
| 국내 허가 적응증/용법용량/금기/ATC | `openapi_mfds_get_drug_indication` | 한국 사용자 질의의 최종 근거(source of truth)로 우선 채택. DailyMed 기반 미국 적응증과 다를 경우 반드시 병기하여 국가를 라벨링 |
| FAERS 이상반응 보고 건수 조회 | `rag_sql_query` (`faers_12q4_25q4`) | 단순 COUNT 결과를 "부작용 발생률"처럼 제시하지 않고, 위 5개 caveat(보고 건수≠발생률, 인과관계 미확정, 중복/편향 가능성, 신호탐지 지표 필요성, 공식 라벨과 병행 확인)을 답변 템플릿에 고정 포함. 가능하면 `rag_get_data_source_detail`로 schema를 먼저 확인해 어떤 컬럼(성분/제품/이상반응명/보고일 등)으로 조회 가능한지 파악 후 SQL 작성 |
| 미·한 데이터 상충 시 처리 | `adr_retrieve_drug_info` + `openapi_mfds_get_drug_indication` 병행 호출 | 두 결과를 각각 "미국 FDA 라벨 기준" / "한국 식약처 허가사항 기준"으로 라벨링해 병기, 자동 종합·단정 금지 |

## 출처
- [About DailyMed - NIH](https://dailymed.nlm.nih.gov/dailymed/about-dailymed.cfm)
- [DailyMed RESTful Web Services - /spls API](https://dailymed.nlm.nih.gov/dailymed/webservices-help/v2/spls_api.cfm)
- [DailyMed - SPL Resources](https://dailymed.nlm.nih.gov/dailymed/spl-resources.cfm)
- [Adverse Reactions Section of Labeling for Human Prescription Drug and Biological Products — FDA Guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/adverse-reactions-section-labeling-human-prescription-drug-and-biological-products-content-and)
- [Section Headings (LOINC) | FDA](https://www.fda.gov/industry/structured-product-labeling-resources/section-headings-loinc)
- [LOINC 34066-1 Boxed Warning](https://loinc.org/34066-1)
- [LOINC 34067-9 Indications and Usage](https://loinc.org/34067-9)
- [LOINC 34068-7 Dosage and Administration](https://loinc.org/34068-7)
- [LOINC 34070-3 Contraindications](https://loinc.org/34070-3)
- [식품의약품안전처_의약품 제품 허가정보 - 공공데이터포털](https://www.data.go.kr/data/15095677/openapi.do)
- [식의약 데이터 포털 - 식품의약품안전처](https://data.mfds.go.kr/)
- [의약품 공공데이터공개 - 의약품안전나라](https://nedrug.mfds.go.kr/cntnts/80)
- [의약품안전나라 통합검색](https://nedrug.mfds.go.kr/searchDrug)
- [식품의약품안전처_의약품개요정보(e약은요) - 공공데이터포털](https://www.data.go.kr/tcs/dss/selectApiDataDetailView.do?publicDataPk=15075057)
- [ATC 코드 - 위키백과](https://ko.wikipedia.org/wiki/ATC_%EC%BD%94%EB%93%9C)
- [심평원, 2021년 3분기 '의약품 ATC 코드' 목록 공개 - HIRA](https://www.hira.or.kr/bbsDummy.do?pgmid=HIRAA020041000100&brdScnBltNo=4&brdBltNo=10512&pageIndex=1)
- [프로페시아정1밀리그램 허가사항 - 의약품안전나라](https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetailCache?cacheSeq=200009059aupdateTs2022-11-09+11:20:43.0b)
- [탈모약 프로페시아와 아보다트 비교 - 데일리팜](https://www.dailypharm.com/Users/News/NewsView.html?ID=177709)
- [프로스카→프로페시아 편법처방 여전 - 데일리팜](https://m.dailypharm.com/News/209240)
- [The FDA Adverse Event Reporting System (FAERS) Explained - IntuitionLabs](https://intuitionlabs.ai/articles/fda-adverse-event-reporting-system)
- [Utility and limitations of the FDA adverse events reporting system public dashboard for safety analyses](https://www.tandfonline.com/doi/full/10.1080/14740338.2025.2588634)
- [Benefits and strengths of the disproportionality analysis for identification of adverse drug reactions - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC3244636/)
- [The reporting odds ratio and its advantages over the proportional reporting ratio - Rothman 2004 - Pharmacoepidemiology and Drug Safety](https://onlinelibrary.wiley.com/doi/10.1002/pds.1001)
- [Conducting and interpreting disproportionality analyses derived from spontaneous reporting systems - Frontiers](https://www.frontiersin.org/journals/drug-safety-and-regulation/articles/10.3389/fdsfr.2023.1323057/full)
- [What Are the Limitations of the FAERS Database?](https://medxdrg.com/what-are-the-limitations-of-the-faers-database)
- [미국 FDA도 인정한 혁신 신약, 왜 한국 식약처 문턱 앞에서 걸리는가 - 뉴스비전e (조인트스템 사례)](https://www.nvp.co.kr/news/articleView.html?idxno=318905)
- [의약품 첨부 문서의 국가별 운영 현황과 시사점 - BioIN](https://bioin.or.kr/board.do?bid=policy&cPage=84&cate1=all&cate2=all2&cmd=view&num=289130&s_str=)

> 참고: DailyMed API 실제 응답 스키마(section별 구조화 여부), MFDS OpenAPI의 정확한 "허가상태/취하" 필드명 및 값 체계는 검색만으로 완전히 확인하지 못했다 — Swagger 명세 원문 또는 대회 MCP tool의 실제 호출 결과로 추가 검증 필요.
