# Research Intelligence end-to-end validation

Environment: `local-isolated`. Pipeline version: `2.0.0`. Commit SHA: `2feb52a418f6011c30cd002677f01033182847b6` (working tree includes uncommitted pipeline changes).
This report contains actual run records. It is not a staging PASS when the environment is local.
Local database: PostgreSQL 17 in Docker container `archipelago-ri-validation` on `127.0.0.1:15432`, backed by named volume `archipelago-ri-validation-data`. PDF artifacts and derived projections are under `/tmp/archipelago-ri-validation/`; the machine-readable run summaries are saved in this repository.

## Test accounts / roles

Jobs were submitted as `local-validation-faculty` with stored role `faculty`. No live Supabase staff or student session was available for staging authorization tests.

## Optical Character Recognition

Job: `d4fe9685-7a52-43a7-93f0-47222ab5ce4b`; result: **PARTIAL**; status: `partial`.

Candidates: `{'metadata_only': 45, 'raw_candidates': 46, 'fulltext_parsed': 1, 'fulltext_deferred': 0, 'fulltext_eligible': 1, 'duplicates_removed': 0, 'evidence_validated': 0, 'fulltext_attempted': 1, 'identity_conflicts': 0, 'metadata_validated': 46, 'canonical_candidates': 46, 'fulltext_fetch_failed': 0, 'fulltext_parse_failed': 0}`. Displayed: **10**.

Sources: openalex=live (HTTP 200, records 25); crossref=live (HTTP 200, records 21); arxiv=request_failed (HTTP None, records 0); semantic_scholar=rate_limited (HTTP 429, records 0)

Coverage gaps: arxiv, extractor_version_not_recorded_in_initial_run, fewer_than_three_identity_merges, fewer_than_two_extracted_fulltext_assertions, no_human_validated_evidence, semantic_scholar

Full records, shortlists, identities, evidence, and features: `optical-character-recognition.json`.

### Source request evidence

| Source | Requested at | HTTP | Request ID | Raw SHA-256 |
|---|---|---:|---|---|
| openalex | 2026-10-17T02:17:41.845855+00:00 | 200 | — | `93827ca7f61717bea1973b0630188313d2c5100c2a5b16f988ddde5622e97d98` |
| crossref | 2026-10-17T02:17:44.482952+00:00 | 200 | — | `3659387a526c6c6b3f56da4e98e728e84f4c6626abe792946efc71af1f96c363` |
| arxiv | 2026-10-17T02:17:46.081534+00:00 | — | — | `—` |
| semantic_scholar | 2026-10-17T02:18:01.438476+00:00 | 429 | f5944d41-91d5-4fc2-a937-3f256a76c622 | `65ab993d12c5c2cc9b68e6da2bb79b326930283e520363ffcdc145f88cd5a148` |

### Actual displayed papers

| Rank | Title | Year | DOI / arXiv | Access | Pipeline state | Relevance reason |
|---:|---|---:|---|---|---|---|
| 1 | A Review: Optical Character Recognition | 2018 | 10.5281/zenodo.1213077 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 2 | Optical Character Recognition of Amharic Documents | 2007 | 10.5130/ajict.v3i2.543 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 3 | Optical Character Recognition by Open source OCR Tool Tesseract: A Case Study | 2012 | 10.5120/8794-2784 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 4 | Optical Character Recognition | 1990 | 10.1177/0145482x9008401004 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 5 | Optical character recognition | 1973 | 10.1088/0031-9112/24/5/012 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 6 | Image Thresholding for Optical Character Recognition and Other Applications Requiring Character Image Extraction | 1983 | 10.1147/rd.274.0400 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 7 | OPTICAL CHARACTER RECOGNITION | 1971 | 10.1108/eb000971 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 8 | A Detailed Analysis of Optical Character Recognition Technology | 2016 | 10.18100/ijamec.270374 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 9 | Improved Discrimination in Optical Character Recognition | 1969 | 10.1364/ao.8.002354 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 10 | A Survey on Optical Character Recognition System | 2017 | 10.48550/arxiv.1710.05703 | FULLTEXT_PARSED | FULLTEXT_PARSED | title query coverage 1.00; abstract query coverage 1.00 |

Identity merges demonstrated: **0 / 3 requested**. Full-text assertion examples: **1 / 2 requested**. Feature dumps: **3 papers**. Evidence states: `{'pending_review': 1}`.

- Evidence `4a8975bd-3835-540b-8281-808c15e9043a`: `pending_review`; page 1, section abstract, artifact `41e389e01cb3114b421c501f649daeec93c826edc709cef53ceeef9e16aeb751`, extractor `not recorded`; Abstract—Optical Character Recognition (OCR) has been a topic of interest for many years

## Pedestrian Detection

Job: `841b6883-83b9-495c-8af1-00dd7723d5db`; result: **PARTIAL**; status: `partial`.

Candidates: `{'metadata_only': 92, 'raw_candidates': 106, 'fulltext_parsed': 8, 'fulltext_deferred': 7, 'fulltext_eligible': 15, 'duplicates_removed': 2, 'evidence_validated': 0, 'fulltext_attempted': 8, 'identity_conflicts': 0, 'metadata_validated': 100, 'canonical_candidates': 100, 'fulltext_fetch_failed': 0, 'fulltext_parse_failed': 0}`. Displayed: **10**.

Sources: openalex=live (HTTP 200, records 19); crossref=live (HTTP 200, records 37); arxiv=request_failed (HTTP None, records 0); semantic_scholar=live (HTTP 200, records 50)

Coverage gaps: arxiv, extractor_version_not_recorded_in_initial_run, fewer_than_three_identity_merges, fulltext_processing_deferred, no_human_validated_evidence

Full records, shortlists, identities, evidence, and features: `pedestrian-detection.json`.

### Source request evidence

| Source | Requested at | HTTP | Request ID | Raw SHA-256 |
|---|---|---:|---|---|
| openalex | 2026-10-17T02:19:00.471440+00:00 | 200 | — | `46b370e47a0751765c255f0ddc06443157fe3ca9ded9ae99930b4036dde2c4a6` |
| crossref | 2026-10-17T02:19:03.078113+00:00 | 200 | — | `b57bc394afdc8a801f0c46a295e0c17f3e27b0c58be94d3f2b7ac536c6827b6a` |
| arxiv | 2026-10-17T02:19:04.782481+00:00 | — | — | `—` |
| semantic_scholar | 2026-10-17T02:19:20.150616+00:00 | 200 | 01f3d339-e51b-42f4-8d8a-bfd0a6072694 | `f8b56e316dda93b37283112695cbe79cd066d3e17a6b4dbee5210203028797d5` |

### Actual displayed papers

| Rank | Title | Year | DOI / arXiv | Access | Pipeline state | Relevance reason |
|---:|---|---:|---|---|---|---|
| 1 | When Pedestrian Detection Meets Multi-Modal Learning: Generalist Model and Benchmark Dataset | 2024 | 10.48550/arXiv.2407.10125 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 2 | Survey of pedestrian detection with occlusion | 2020 | 10.1007/s40747-020-00206-8 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 3 | Robust Pedestrian Detection via Constructing Versatile Pedestrian Knowledge Bank | 2024 | 10.1016/j.patcog.2024.110539 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 4 | Cascade Transformer Decoder Based Occluded Pedestrian Detection With Dynamic Deformable Convolution and Gaussian Projection Channel Attention Mechanism | 2023 | 10.1109/TMM.2023.3251100 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 5 | M2FNet: Mask-Guided Multi-Level Fusion for RGB-T Pedestrian Detection | 2024 | 10.1109/TMM.2024.3381377 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 6 | Pedestrian detection by using weighted channel features with hierarchical region reduction | — | 10.58837/chula.the.2014.888 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 7 | Multispectral Pedestrian Detection via Simultaneous Detection and Segmentation | 2018 | 10.48550/arxiv.1808.04818 | FULLTEXT_PARSED | FULLTEXT_PARSED | title query coverage 1.00; abstract query coverage 1.00 |
| 8 | Uncertainty-Guided Cross-Modal Learning for Robust Multispectral Pedestrian Detection | 2022 | 10.1109/TCSVT.2021.3076466 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 9 | TFDet: Target-Aware Fusion for RGB-T Pedestrian Detection | 2023 | 10.1109/TNNLS.2024.3443455 | FULLTEXT_PARSED | FULLTEXT_PARSED | title query coverage 1.00; abstract query coverage 1.00 |
| 10 | Survey of Pedestrian Detection for Advanced Driver Assistance Systems | 2009 | 10.1109/tpami.2009.122 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |

Identity merges demonstrated: **2 / 3 requested**. Full-text assertion examples: **2 / 2 requested**. Feature dumps: **3 papers**. Evidence states: `{'pending_review': 8}`.

- Merge `7923540d-8864-5d41-80eb-41679577b4d4` from 2 records: exact_doi_match
- Merge `7f0cd907-1f2c-5fb5-8549-3b0b21584dcc` from 2 records: exact_doi_match
- Evidence `1f693a6a-8b45-5701-9667-6fcd678879d1`: `pending_review`; page 1, section abstract, artifact `4a7f2787715f4f32a3408dd5d2951657c6fb282e6082f370a9b0dc34e45808cf`, extractor `not recorded`; Abstract Multispectral pedestrian detection has attracted increasing attention from the research community due to its crucial competence for many arou
- Evidence `25528aac-2e98-5083-bd4c-09f5a5acc498`: `pending_review`; page 1, section abstract, artifact `577a28ab3775f0ecedb9169208262a910af2a667e6aa2c30528543fec48cb8a1`, extractor `not recorded`; Abstract—Pedestrian detection plays a critical role in com- puter vision as it contributes to ensuring traffic safety

## Bengali Speech Recognition

Job: `0dcc9ab7-b4e4-4b3a-99dc-e3fa871f9ed2`; result: **PARTIAL**; status: `partial`.

Candidates: `{'metadata_only': 49, 'raw_candidates': 64, 'fulltext_parsed': 8, 'fulltext_deferred': 1, 'fulltext_eligible': 9, 'duplicates_removed': 7, 'evidence_validated': 0, 'fulltext_attempted': 8, 'identity_conflicts': 0, 'metadata_validated': 57, 'canonical_candidates': 57, 'fulltext_fetch_failed': 0, 'fulltext_parse_failed': 0}`. Displayed: **10**.

Sources: openalex=live (HTTP 200, records 19); crossref=live (HTTP 200, records 45); arxiv=rate_limited (HTTP 429, records 0); semantic_scholar=rate_limited (HTTP 429, records 0)

Coverage gaps: arxiv, extractor_version_not_recorded_in_initial_run, fulltext_processing_deferred, no_human_validated_evidence, semantic_scholar

Full records, shortlists, identities, evidence, and features: `bengali-speech-recognition.json`.

### Source request evidence

| Source | Requested at | HTTP | Request ID | Raw SHA-256 |
|---|---|---:|---|---|
| openalex | 2026-10-17T02:19:48.645302+00:00 | 200 | — | `54c9955c4215abff5a0fd68eb33ad7779015a23d3f8802a053e28c7a7e7ce269` |
| crossref | 2026-10-17T02:19:50.668629+00:00 | 200 | — | `f1a0c4e44c958f5bd078f38557e99d26971ad730afc7d6d897a1f3c5c23ff4ed` |
| arxiv | 2026-10-17T02:19:52.234359+00:00 | 429 | — | `467622e2f17f01d302d6c790b13078569f17d71cd83910558535019a594e07c1` |
| semantic_scholar | 2026-10-17T02:19:52.824161+00:00 | 429 | 173d5fca-d939-40ac-b1b4-0042be825169 | `65ab993d12c5c2cc9b68e6da2bb79b326930283e520363ffcdc145f88cd5a148` |

### Actual displayed papers

| Rank | Title | Year | DOI / arXiv | Access | Pipeline state | Relevance reason |
|---:|---|---:|---|---|---|---|
| 1 | Automatic Speech Recognition for Biomedical Data in Bengali Language | 2024 | 10.48550/arxiv.2406.12931 | FULLTEXT_PARSED | FULLTEXT_PARSED | title query coverage 1.00; abstract query coverage 1.00 |
| 2 | End-to-End Bengali Speech Recognition | 2020 | 10.48550/arxiv.2009.09615 | FULLTEXT_PARSED | FULLTEXT_PARSED | title query coverage 1.00; abstract query coverage 1.00 |
| 3 | Multi-Level Embedding Conformer Framework for Bengali Automatic Speech Recognition | 2025 | 10.48550/arxiv.2601.09710 | FULLTEXT_ELIGIBLE | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 4 | A BCI system for imagined Bengali speech recognition | 2023 | 10.1016/j.mlwa.2023.100486 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 5 | BanglaNum -- A Public Dataset for Bengali Digit Recognition from Speech | 2024 | 10.48550/arxiv.2403.13465 | FULLTEXT_PARSED | FULLTEXT_PARSED | title query coverage 1.00; abstract query coverage 1.00 |
| 6 | Effect of vocal tract dynamics on neural network‐based speech recognition: A Bengali language‐based study | 2022 | 10.1111/exsy.13045 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 7 | Lightweight Machine Learning Model for Speech Emotion Recognition in English and Bengali Language | 2026 | 10.2139/ssrn.7371999 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 8 | Bengali Common Voice Speech Dataset for Automatic Speech Recognition | 2022 | 10.48550/arxiv.2206.14053 | FULLTEXT_PARSED | FULLTEXT_PARSED | title query coverage 1.00; abstract query coverage 1.00 |
| 9 | Challenges and Opportunities of Speech Recognition for Bengali Language | 2021 | 10.48550/arxiv.2109.13217 | FULLTEXT_PARSED | FULLTEXT_PARSED | title query coverage 1.00; abstract query coverage 1.00 |
| 10 | An Automatic Speech Recognition System for Bengali Language based on Wav2Vec2 and Transfer Learning | 2022 | 10.48550/arxiv.2209.08119 | FULLTEXT_PARSED | FULLTEXT_PARSED | title query coverage 1.00; abstract query coverage 1.00 |

Identity merges demonstrated: **3 / 3 requested**. Full-text assertion examples: **2 / 2 requested**. Feature dumps: **3 papers**. Evidence states: `{'pending_review': 3, 'provenance_checked': 5}`.

- Merge `c27a2b29-c508-551f-881f-831171ecc717` from 2 records: exact_doi_match
- Merge `66c2fc12-6d4e-5a40-b005-0e0e582bf1ad` from 2 records: exact_doi_match
- Merge `35f5b272-4397-592f-be0b-d8d136cbd697` from 2 records: exact_doi_match
- Evidence `8e737f6a-1425-58f8-8d04-938df0ed3306`: `pending_review`; page 1, section abstract, artifact `00554f8fb10ccf2616aa2834c1759417c8280c871b69c864b643e49ffcaf90c4`, extractor `not recorded`; Abstract Bengali is one of the most spoken languages in the world with over 300 million speakers globally
- Evidence `9e1e477d-c0c3-5975-a8ec-247284885ad1`: `pending_review`; page 1, section abstract, artifact `ed14302f01879bad94c167637a3a3b5d49dd51aae4882e0c268843ad6faba0f5`, extractor `not recorded`; Abstract Speech recognition is a fascinating process that offers the opportunity to interact and command the machine in the field of human-computer in

## Skin Cancer Detection

Job: `5c88a064-1ec0-40e7-b2cd-c9f01a147fd5`; result: **PARTIAL**; status: `partial`.

Candidates: `{'metadata_only': 64, 'raw_candidates': 65, 'fulltext_parsed': 0, 'fulltext_deferred': 0, 'fulltext_eligible': 0, 'duplicates_removed': 1, 'evidence_validated': 0, 'fulltext_attempted': 0, 'identity_conflicts': 0, 'metadata_validated': 64, 'canonical_candidates': 64, 'fulltext_fetch_failed': 0, 'fulltext_parse_failed': 0}`. Displayed: **10**.

Sources: openalex=live (HTTP 200, records 36); crossref=live (HTTP 200, records 29); arxiv=request_failed (HTTP None, records 0); semantic_scholar=rate_limited (HTTP 429, records 0)

Coverage gaps: arxiv, fewer_than_three_identity_merges, fewer_than_two_extracted_fulltext_assertions, no_human_validated_evidence, semantic_scholar

Full records, shortlists, identities, evidence, and features: `skin-cancer-detection.json`.

### Source request evidence

| Source | Requested at | HTTP | Request ID | Raw SHA-256 |
|---|---|---:|---|---|
| openalex | 2026-10-17T02:20:06.373776+00:00 | 200 | — | `3c8275d087e0ab92da407a399dd0d9b012f293bf629ad4b88d2358504cdb6491` |
| crossref | 2026-10-17T02:20:09.223279+00:00 | 200 | — | `4e903d7a6f7963c338373b8143ba65c6dfa9067ae8c5175d117b8d9a233852d8` |
| arxiv | 2026-10-17T02:20:10.904486+00:00 | — | — | `—` |
| semantic_scholar | 2026-10-17T02:20:26.111721+00:00 | 429 | 38fc9dc2-236e-4fba-bae6-f8f882e8e905 | `65ab993d12c5c2cc9b68e6da2bb79b326930283e520363ffcdc145f88cd5a148` |

### Actual displayed papers

| Rank | Title | Year | DOI / arXiv | Access | Pipeline state | Relevance reason |
|---:|---|---:|---|---|---|---|
| 1 | Skin Cancer Detection: A Survey | 2023 | 10.37648/ijrst.v13i01.001 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 2 | Skin Cancer Detection: A Review Using Deep Learning Techniques | 2021 | 10.3390/ijerph18105479 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 3 | A Deep Learning Approach to Skin Cancer Detection in Dermoscopy Images | 2020 | 10.31661/jbpe.v0i0.2004-1107 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 4 | Raman microspectroscopy for skin cancer detection in vitro | 2008 | 10.1117/1.2899155 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 5 | Artificial Intelligence for Skin Cancer Detection: Scoping Review | 2021 | 10.2196/22934 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 6 | Real time THz imaging—opportunities and challenges for skin cancer detection | 2021 | 10.1063/5.0055259 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 7 | Melanoma Skin Cancer Detection using Deep Learning | 2022 | 10.1101/2022.02.02.22269505 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 8 | Skin Cancer Detection Based on Deep Learning | 2022 | 10.31661/jbpe.v0i0.2207-1517 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 9 | Skin cancer detection using deep machine learning techniques | 2024 | 10.1016/j.ibmed.2024.100191 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 10 | AI in dermatology: a comprehensive review into skin cancer detection | 2024 | 10.7717/peerj-cs.2530 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |

Identity merges demonstrated: **1 / 3 requested**. Full-text assertion examples: **0 / 2 requested**. Feature dumps: **3 papers**. Evidence states: `{}`.

- Merge `b7c4651b-16a2-5a5f-b39f-0733cd905efd` from 2 records: exact_doi_match

## Fake News Detection

Job: `0ffe8a19-3adb-46d8-887e-96e90ee92525`; result: **PARTIAL**; status: `partial`.

Candidates: `{'metadata_only': 43, 'raw_candidates': 47, 'fulltext_parsed': 4, 'fulltext_deferred': 0, 'fulltext_eligible': 4, 'duplicates_removed': 0, 'evidence_validated': 0, 'fulltext_attempted': 4, 'identity_conflicts': 0, 'metadata_validated': 47, 'canonical_candidates': 47, 'fulltext_fetch_failed': 0, 'fulltext_parse_failed': 0}`. Displayed: **10**.

Sources: openalex=live (HTTP 200, records 23); crossref=live (HTTP 200, records 24); arxiv=request_failed (HTTP None, records 0); semantic_scholar=rate_limited (HTTP 429, records 0)

Coverage gaps: arxiv, extractor_version_not_recorded_in_initial_run, fewer_than_three_identity_merges, no_human_validated_evidence, semantic_scholar

Full records, shortlists, identities, evidence, and features: `fake-news-detection.json`.

### Source request evidence

| Source | Requested at | HTTP | Request ID | Raw SHA-256 |
|---|---|---:|---|---|
| openalex | 2026-10-17T02:20:31.500953+00:00 | 200 | — | `bb301592b17730c4f26a5970a7c0bc4f21e960064d45ea9385a46381c1cbbd9b` |
| crossref | 2026-10-17T02:20:34.144607+00:00 | 200 | — | `789e78c0a615a19d5f24d31827e583a3e6467418963caffdb07db98648928077` |
| arxiv | 2026-10-17T02:20:35.452660+00:00 | — | — | `—` |
| semantic_scholar | 2026-10-17T02:20:50.739171+00:00 | 429 | 6fec80e8-1647-4227-b427-aa12ac96548a | `65ab993d12c5c2cc9b68e6da2bb79b326930283e520363ffcdc145f88cd5a148` |

### Actual displayed papers

| Rank | Title | Year | DOI / arXiv | Access | Pipeline state | Relevance reason |
|---:|---|---:|---|---|---|---|
| 1 | Fake news detection: a survey of evaluation datasets | 2021 | 10.7717/peerj-cs.518 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 2 | Network-based Fake News Detection | 2019 | 10.1145/3373464.3373473 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 3 | AI for Automatic Detection of Fake News and Misinformation | 2025 | 10.36227/techrxiv.173687875.54963646/v1 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 4 | Fake News Detection on Social Media: A Data Mining Perspective | 2017 | 10.48550/arxiv.1708.01967 | FULLTEXT_PARSED | FULLTEXT_PARSED | title query coverage 1.00; abstract query coverage 1.00 |
| 5 | Supervised Learning for Fake News Detection | 2019 | 10.1109/mis.2019.2899143 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 6 | Sentiment Analysis for Fake News Detection | 2021 | 10.3390/electronics10111348 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 7 | Unsupervised Fake News Detection Based on Autoencoder | 2021 | 10.1109/access.2021.3058809 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 8 | Fake News Detection | 2022 | 10.21203/rs.3.rs-1533870/v1 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 9 | A Comprehensive Review on Fake News Detection With Deep Learning | 2021 | 10.1109/access.2021.3129329 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |
| 10 | An Integrated Multi-Task Model for Fake News Detection | 2021 | 10.1109/tkde.2021.3054993 | METADATA_ONLY | METADATA_VALIDATED | title query coverage 1.00; abstract query coverage 1.00 |

Identity merges demonstrated: **0 / 3 requested**. Full-text assertion examples: **2 / 2 requested**. Feature dumps: **3 papers**. Evidence states: `{'pending_review': 1, 'provenance_checked': 3}`.

- Evidence `f7acfd64-a1d5-59b3-ae48-248515ab88cd`: `pending_review`; page 1, section abstract, artifact `acff39937bcd754041bd8080190334e90a41ee2ae7d54eaff7ba15f7ae4a5309`, extractor `not recorded`; Abstract Social media are nowadays one of the main news sources for millions of people around the globe due to their low cost, easy access, and rapid
- Evidence `49d822e5-d7c4-58a4-9a90-ab968a44c63f`: `provenance_checked`; page 1, section abstract, artifact `a403268f57cd4097aad2efa58303220a0aff101b91759204246f5ff58a51d3e3`, extractor `not recorded`; ABSTRACT Social media for news consumption is a double-edged sword

## Graph validation

Latest projection pointer: `{'counts': {'authors': 849, 'claims': 0, 'datasets': 0, 'evidence': 0, 'papers': 314, 'venues': 196}, 'generation': 'research-445032ee25674a1ea19a867371ac03de', 'graph_path': '/tmp/archipelago-ri-validation/projections/research-445032ee25674a1ea19a867371ac03de', 'published_at': '2026-10-17T02:28:54.886282+00:00', 'vector': {'count': 314, 'dimensions': 768, 'model': 'Snowflake/snowflake-arctic-embed-m-v1.5', 'path': '/tmp/archipelago-ri-validation/projections/research-445032ee25674a1ea19a867371ac03de.vector-inputs.npz', 'sha256': '90da8cd82db0c85ba66272c862990eff9165a05bbff854840263b035baf90a5a', 'state': 'ready'}, 'vector_inputs_path': '/tmp/archipelago-ri-validation/projections/research-445032ee25674a1ea19a867371ac03de.vector-inputs.jsonl'}`.

PostgreSQL → Kùzu delete/rebuild trace: `{'postgres_papers': 314, 'first_build': {'papers': 314, 'authors': 849, 'venues': 196, 'datasets': 0, 'claims': 0, 'evidence': 0}, 'second_build': {'papers': 314, 'authors': 849, 'venues': 196, 'datasets': 0, 'claims': 0, 'evidence': 0}, 'first_nodes': 314, 'second_nodes': 314, 'pass': True}`.

Representative paper/author/venue edge traces for all five topics: `{'optical character recognition': {'paper_id': '05b5baf2-d84c-5aff-b28c-a91fba599f84', 'title': 'A Review: Optical Character Recognition', 'postgres_authoritative': True, 'kuzu_paper_nodes': 1, 'authored_by_edges': 1, 'published_in_edges': 1, 'projection_generation': 'research-445032ee25674a1ea19a867371ac03de'}, 'pedestrian detection': {'paper_id': '00b98ffd-37b3-5385-89b7-ba36bb09713b', 'title': 'When Pedestrian Detection Meets Multi-Modal Learning: Generalist Model and Benchmark Dataset', 'postgres_authoritative': True, 'kuzu_paper_nodes': 1, 'authored_by_edges': 6, 'published_in_edges': 1, 'projection_generation': 'research-445032ee25674a1ea19a867371ac03de'}, 'bengali speech recognition': {'paper_id': '1bc13457-b174-599c-a891-451f4c25f346', 'title': 'Automatic Speech Recognition for Biomedical Data in Bengali Language', 'postgres_authoritative': True, 'kuzu_paper_nodes': 1, 'authored_by_edges': 4, 'published_in_edges': 1, 'projection_generation': 'research-445032ee25674a1ea19a867371ac03de'}, 'skin cancer detection': {'paper_id': '06be372a-72ab-5670-9c56-406f639443b6', 'title': 'Skin Cancer Detection: A Survey', 'postgres_authoritative': True, 'kuzu_paper_nodes': 1, 'authored_by_edges': 1, 'published_in_edges': 1, 'projection_generation': 'research-445032ee25674a1ea19a867371ac03de'}, 'fake news detection': {'paper_id': '0064c6c7-cdb8-5b95-8173-e987e00af3f7', 'title': 'Fake news detection: a survey of evaluation datasets', 'postgres_authoritative': True, 'kuzu_paper_nodes': 1, 'authored_by_edges': 4, 'published_in_edges': 1, 'projection_generation': 'research-445032ee25674a1ea19a867371ac03de'}}`.

Vector smoke: optical character recognition → Optical character recognition (1.000); pedestrian detection → Pedestrian detection and tracking at crossroads (0.786); bengali speech recognition → State of art Research in Bengali Speech Recognition (0.812); skin cancer detection → Skin Cancer Detection Technology (0.953); fake news detection → Online Fake News Detection (0.937)

The graph currently projects paper, author, and venue metadata. No claim/evidence edges were published because no extraction passed human adjudication. Citation, benchmark, and semantic relation edges remain unimplemented.

## Automatic refresh validation

A tracked OCR topic was made due in the isolated database and one `work_cycle` queued and processed it. OpenAlex and Crossref refreshed live; arXiv and Semantic Scholar returned 429. The cycle published a new Kùzu/vector generation from PostgreSQL.

This verifies one worker cycle, not continuous operation. No scheduler or worker was deployed, and staff access remains disabled pending the release gate.

[Refresh cycle trace](../../artifacts/validation/research-intelligence/refresh-cycle.json) (generation `research-445032ee25674a1ea19a867371ac03de`).

## Bibliometrics and feature validation

Per-paper feature observations include missing states and formula inputs in each JSON file. Author h-index/g-index/i10/m-index snapshots are not implemented. The topic shortlist reads only title and abstract query coverage; the local ordering test confirms that citation count and author reputation do not affect it.

## Access control validation

Automated four-role route tests ran locally. The DB-backed Flask route probe used simulated verified principals: all five direct student requests returned 403; faculty job/feature/evidence reads and librarian/admin manager reads succeeded. Job creation and refresh actions produced PostgreSQL audit rows. Live Supabase staff/student account tests remain open.

[DB-backed access trace](../../artifacts/validation/research-intelligence/access-control.json) (pass: `True`).

## Institutional source status

OPAC and IEM CRP were checked read-only. No approved machine-readable export path or session credential was available, so no institutional book/holding data was ingested.

Observed endpoint states: `{'opac': {'url': 'https://uemk-opac.l2c2.co.in/', 'checked_at': '2026-10-17T02:25:38.475385+00:00', 'http_status': None, 'state': 'request_failed', 'error': 'ConnectTimeout'}, 'iemcrp': {'url': 'https://iemcrp.com/', 'checked_at': '2026-10-17T02:25:49.053486+00:00', 'http_status': 403, 'location': None, 'state': 'http_error'}}`.

Apify public-page probes: opac-https-apify.json → source_request_failed (timeout; 0 dataset items, 0 records); opac-http-apify.json → unavailable (ABORTED; 0 dataset items, 0 records); iemcrp-apify.json → source_request_failed (http_403; 0 dataset items, 0 records)

The Actor's own `SUCCEEDED` status does not establish a successful source fetch. The HTTPS OPAC probe timed out, the HTTP OPAC probe was stopped after two minutes with zero pages, and the public IEM portal returned HTTP 403. No book or holding was inferred from any of these runs. The actor trace JSON files preserve run IDs, cost, dataset counts, and failure states without storing tokens.

## Failures / coverage gaps and final decision

Focused auth/research tests: 38 passed. Repository-wide Ruff lint and formatting passed. Strict mypy passed on the touched research modules; the repository-wide strict-mypy quality gate still has an existing baseline of unrelated errors.

**PARTIAL.** Local ingestion is inspectable; the required staging run, live role tests, human evidence adjudication, GROBID/selective OCR, and institutional OPAC/IEM ingestion remain release gates. The research projection is not yet wired into chat retrieval. Research Intelligence stays disabled.
