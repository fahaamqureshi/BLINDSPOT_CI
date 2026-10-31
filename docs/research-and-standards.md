# Research and standards behind BLINDSPOT CI

Checked 2026-10-31. This page says what the literature and industry practice ask of a vision test tool,
what this project now does about it, and what it still does not.

## How these sources were read

- Qiao et al. (reference 4) was read in full on arXiv (version 1 tables).
- The other sources were read as titles, abstracts and publisher or index summaries found by search.
  Their findings below are paraphrased from those summaries. Open the paper before quoting a number
  in a submission.
- Standards (references 23 to 26) were read through the European Commission service desk page and
  secondary summaries. The paid texts (ISO 21448) and the NIST PDF were not read directly.
- Nothing here was copied. Wording is original.

## What the sources say and what the project does

| Finding | Source | In this project |
| --- | --- | --- |
| Models that score alike on a test set can behave differently in deployment, so aggregate scores hide risk | 21 | Reports are sliced by condition, never one number |
| Behavioral tests by capability find bugs that held-out accuracy misses | 9 | Cases are named conditions (low light, occlusion, truncated, small, absent) |
| Systematic errors cluster in slices that can be found and described | 7 | Per-condition table, failures listed with the condition |
| Standard corruptions at five severities make robustness comparable | 5, 6 | `corrupt-gen`: low light, noise, blur, JPEG, fog, contrast at severities 1 to 5 |
| SAM (version 1, point prompts) held up under most corruptions but dropped for zoom blur, contrast, JPEG and heavy occlusion | 4 | Contrast and JPEG are in the corruption set. Occlusion is a labeled real condition, not a synthetic patch, because a patch changes the truth |
| Small samples need exact intervals, not Wald intervals | 19 | Wilson 95 percent intervals on every pass count |
| Underpowered comparisons are common and mislead | 18 | Slices with fewer than 5 scored cases are flagged underpowered |
| Test sets contain label errors that can change conclusions | 17 | Human provenance on every label, a reviewer field, hash lock against edits, a review count in the card |
| Generated or LLM-written judgments carry position, verbosity and self-preference bias | 13 | No model grades anything. Python scores. Wonder and Voice never change a score |
| Choosing which tests to run is a decision with a cost, and chance is the baseline | 8 | `compare-agent`: exact hypergeometric comparison of the agent against random order |
| Reasoning plus tool use is a working agent pattern | 20 | Muse Spark picks tests by function calling and sees each result |
| Excessive agency is a top LLM application risk | 26 | Two tools only, validated arguments, bounded steps, spend cap, no free-form actions |
| Model cards and datasheets are the expected documentation | 15, 16, 27 | `card` command and download link: intended use, data, metrics, limits |
| A production readiness rubric scores the weakest section, not the average | 22 | The card lists evidence gaps next to results |
| Perception failures are organized by triggering conditions (SOTIF) | 25 | Conditions are the triggering conditions of this tool |
| Distribution-free guarantees need a calibration set | 11, 12 | Not implemented. See next steps |
| Boundary-aware metrics expose mask edge errors | 10 | Not implemented. Needs human masks |

## Industry expectations, in practice

- Document intended use, data, metrics and limits for a model (Model Cards, Datasheets, AWS AI Service
  Cards). AWS cards also tell customers to measure a service on their own content, which is exactly the
  job of this tool.
- Show test sets, metrics and tools (NIST AI RMF, MEASURE function). The evaluation card does this.
- Declare accuracy metrics and their limits for high-risk systems (EU AI Act Article 15). The dates the
  rules apply are reported differently by different pages, so check the current timeline before relying
  on one. The card supports documentation only. It does not establish compliance.
- Find the conditions that trigger perception failures before deployment (SOTIF).
- Limit what an agent can do (OWASP LLM06). The agent here can only pick a listed test or stop.

## What the project does not claim

- A pass is one example. A slice with 8 photos and 3 passes has a 95 percent interval of roughly 14 to
  69 percent. Say counts and interval.
- Open Images photos are not a maintenance tray tag. They show how SAM 3.1 handles red safety objects in
  public photos.
- SAM 1 robustness results (reference 4) are hypotheses for SAM 3.1, not findings about it. That paper
  also measured agreement with SAM's own clean masks on 100 photos, not accuracy against human labels.
- Muse Image variants keep a box only on the assumption the edit did not move the object. Measured
  corruptions keep it exactly. Prefer corruptions for numbers.

## Next steps, in order of value

1. A second annotator on at least a third of the labels, with agreement reported (label quality).
2. Repeat each SAM call three times and report any case whose answer changes (repeatability).
3. Human-drawn masks for 20 cases, then Boundary IoU (reference 10).
4. Several prompt wordings per concept, to separate model failure from prompt failure.
5. Conformal risk control (references 11, 12) once there are a few hundred labeled cases.
6. Compare the hosted SAM 3.1 with the open SAM 3 weights (reference 3) for reproducibility.
7. Harden the planner input against hostile case titles in third-party datasets.

## References

Peer-reviewed or archival
1. Kirillov A. et al. Segment Anything. ICCV 2023, pp. 4015 to 4026. arXiv 2304.02643.
2. Ravi N. et al. SAM 2: Segment Anything in Images and Videos. arXiv 2408.00714 (preprint; venue not confirmed here).
3. Carion N. et al. SAM 3: Segment Anything with Concepts. ICLR 2026. arXiv 2511.16719.
4. Qiao Y. et al. Robustness of SAM: Segment Anything Under Corruptions and Beyond. arXiv 2306.07713 (preprint).
5. Hendrycks D., Dietterich T. Benchmarking Neural Network Robustness to Common Corruptions and Perturbations. ICLR 2019. arXiv 1903.12261.
6. Michaelis C. et al. Benchmarking Robustness in Object Detection: Autonomous Driving when Winter is Coming. arXiv 1907.07484 (preprint).
7. Eyuboglu S. et al. Domino: Discovering Systematic Errors with Cross-Modal Embeddings. ICLR 2022. arXiv 2203.14960.
8. Kossen J., Farquhar S., Gal Y., Rainforth T. Active Testing: Sample-Efficient Model Evaluation. ICML 2021. arXiv 2103.05331.
9. Ribeiro M. T., Wu T., Guestrin C., Singh S. Beyond Accuracy: Behavioral Testing of NLP Models with CheckList. ACL 2020, pp. 4902 to 4912.
10. Cheng B., Girshick R., Dollar P., Berg A. C., Kirillov A. Boundary IoU. CVPR 2021, pp. 15334 to 15342. arXiv 2103.16562.
11. Angelopoulos A. N., Bates S., Fisch A., Lei L., Schuster T. Conformal Risk Control. ICLR 2024. arXiv 2208.02814.
12. Bates S., Angelopoulos A., Lei L., Malik J., Jordan M. Distribution-Free, Risk-Controlling Prediction Sets. arXiv 2101.02703.
13. Zheng L. et al. Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. NeurIPS 2023 Datasets and Benchmarks. arXiv 2306.05685.
14. Kuznetsova A. et al. The Open Images Dataset V4. International Journal of Computer Vision 128(7), 2020, pp. 1956 to 1981.
15. Mitchell M. et al. Model Cards for Model Reporting. ACM FAccT 2019 (then named FAT). arXiv 1810.03993.
16. Gebru T. et al. Datasheets for Datasets. Communications of the ACM 64(12), 2021, pp. 86 to 92.
17. Northcutt C. G., Athalye A., Mueller J. Pervasive Label Errors in Test Sets Destabilize Machine Learning Benchmarks. NeurIPS 2021 Datasets and Benchmarks. arXiv 2103.14749.
18. Card D. et al. With Little Power Comes Great Responsibility. EMNLP 2020, pp. 9263 to 9274. arXiv 2010.06595.
19. Brown L. D., Cai T. T., DasGupta A. Interval Estimation for a Binomial Proportion. Statistical Science 16(2), 2001, pp. 101 to 133.
20. Yao S. et al. ReAct: Synergizing Reasoning and Acting in Language Models. ICLR 2023. arXiv 2210.03629.
21. D'Amour A. et al. Underspecification Presents Challenges for Credibility in Modern Machine Learning. JMLR 23(226), 2022. arXiv 2011.03395.
22. Breck E. et al. The ML Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction. IEEE Big Data 2017 (author lists differ between listings).

Standards, regulation and industry practice
23. NIST. Artificial Intelligence Risk Management Framework 1.0. NIST AI 100-1, January 2023. MEASURE function.
24. European Union. Regulation on artificial intelligence (AI Act), Article 15: accuracy, robustness and cybersecurity. Commission AI Act Service Desk page.
25. ISO 21448, Safety of the Intended Functionality (SOTIF). Read through secondary sources and a related paper on perception triggering conditions, arXiv 2303.04037.
26. OWASP. Top 10 for LLM Applications 2025, LLM06 Excessive Agency (secondary summaries read).
27. Amazon Web Services. AI Service Cards, including Amazon Rekognition.

Meta documentation used for the build
28. Meta Model API: models, images, speech-to-text and pricing pages, read 2026-10-31 (dev.meta.ai).
29. Open Images V7 annotation files and per-image license fields (storage.googleapis.com/openimages).
