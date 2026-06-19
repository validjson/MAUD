# E0partial — GPT-5.5 chunked baseline analysis

Per-contract per-field roll-up over **15 contracts** and **1380 single-choice + multilabel cells**.  Aggregate exact-match rate: **1248/1380 = 90.4%**.

## Abstention / commit confusion

How the model's `null`/value choice lined up with gold's `null`/value:

|                          | gold = value | gold = null |
|--------------------------|-------------:|------------:|
| model = matching value  |  1156 | — |
| model = mismatched val. |    79 | **18 hallucinations** |
| model = null            | **35 over-abstentions** |    92 correct |

- **Correct-abstention rate** (cells where gold is null): 92/110 = 83.6%
- **Hallucination rate** (cells where gold is null, model committed): 18/110 = 16.4%
- **Commit rate** (cells where gold has a value): 1235/1270 = 97.2%

## By field role

| Role | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|------|------:|--------:|-----:|--------------:|-------------:|------------:|
| single-choice | 1230 | 1149 | 93.4% | 17 | 24 | 40 |
| multilabel | 150 | 99 | 66.0% | 1 | 11 | 39 |

## Top-10 PCL-risk overlay

The paper's central claim is that fine-tuned models regress specifically on high-PCL-risk fields.  Prediction for E0a: a frontier reasoning model still mis-handles them, even without fine-tuning, because the failure mode lives in the input distribution rather than the training regime.

| Subset | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|--------|------:|--------:|-----:|--------------:|-------------:|------------:|
| Top-10 PCL-risk fields | 150 | 130 | **86.7%** | 17 | 2 | 1 |
| All other fields | 1230 | 1118 | 90.9% | 1 | 33 | 78 |

Top-PCL fields evaluated:

- `absence_of_litigation_closing_condition_governmental_v_non_governmental_answer`
- `absence_of_litigation_closing_condition_pending_v_threatened_v_threatened_in_writing_answer`
- `breach_of_meeting_covenant_required_to_be_willful_material_andor_intentional`
- `breach_of_no_shop_required_to_be_willful_material_andor_intentional`
- `constructive_knowledge_answer`
- `cor_standard_board_determination_only_answer`
- `financial_point_of_view_is_the_sole_consideration`
- `ftr_triggers_answer`
- `knowledge_persons_include_target_management_intervening_event`
- `number_of_additional_matching_rights_periods_for_modifications_ftr`

## Quote-substitution overlay

Across the **13 fields** whose canonical enums contain literal `"` (substituted to `'` for OpenAI and restored to canonical form on disk).  Question: did the substitution bias the model away from those answers?

| Cells where gold is … | Cells | Correct | Rate |
|-----------------------|------:|--------:|-----:|
| a substituted enum value | 117 | 110 | 94.0% |
| a non-substituted value (same fields) | 78 | 71 | 91.0% |

A meaningful gap (e.g. >10pp) below the non-substituted rate is a methodological caveat worth recording in the case study.

## Per-field mismatches

All non-correct cells, up to 50 rows.  Full detail in `analysis.json` under `cells`.

| Contract | Field | Outcome | Pred | Gold |
|----------|-------|---------|------|------|
| contract_103 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['Authority', 'Capitalization-Other', 'No-Conflict` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_103 | `absence_of_litigation_closing_condition_government` | hallucination | `Governmental litigation only` | `null` |
| contract_103 | `absence_of_litigation_closing_condition_pending_v_` | hallucination | `Pending` | `null` |
| contract_103 | `mae_applies_to_target_and_subsidiaries_mae_answer` | wrong_value | `Applies to Target and subsidiaries "taken as a who` | `No` |
| contract_103 | `pandemic_or_other_public_health_event_specific_ref` | wrong_value | `No` | `Yes` |
| contract_103 | `actions_required_under_transaction_agreement_answe` | wrong_value | `Yes` | `No` |
| contract_103 | `liability_standard_for_no_shop_breach_by_target_no` | wrong_value | `Strict liability` | `Reasonable standard` |
| contract_103 | `limitations_on_ftr_exercise_answer` | wrong_value | `['Any breach of no-shop']` | `['Breach of no-shop resulting in a Superior Offer'` |
| contract_103 | `acquisition_proposal_timing_answer` | wrong_value | `['Different Acquisition Proposal - Must sign durin` | `['Same Acquisition Proposal - Must sign during Tai` |
| contract_104 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['Authority', "Brokers' Fee", 'Enforceability', 'N` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_104 | `absence_of_litigation_closing_condition_government` | hallucination | `Governmental litigation only` | `null` |
| contract_104 | `absence_of_litigation_closing_condition_pending_v_` | hallucination | `Pending` | `null` |
| contract_104 | `apc_application_to_answer` | wrong_value | `['announcement', 'consummation']` | `['announcement', 'pendency', 'consummation']` |
| contract_104 | `ordinary_course_efforts_standard_answer` | wrong_value | `Commercially reasonable efforts` | `Flat covenant (no efforts standard)` |
| contract_104 | `application_of_buyer_consent_requirement_negative_` | over_abstain | `null` | `Applies to all negative covenants` |
| contract_104 | `acquisition_proposal_timing_answer` | wrong_value | `['Different Acquisition Proposal - Must sign durin` | `['Same Acquisition Proposal - Must sign during Tai` |
| contract_105 | `accuracy_of_fundamental_target_rws_types_of_rws` | over_abstain | `null` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_105 | `pandemic_or_other_public_health_event_subject_to_d` | wrong_value | `Yes` | `No` |
| contract_105 | `fiduciary_exception_board_determination_standard_a` | wrong_value | `"Inconsistent" with fiduciary duties` | `None` |
| contract_105 | `limitations_on_ftr_exercise_answer` | over_abstain | `null` | `['Breach of no-shop resulting in a Superior Offer'` |
| contract_105 | `initial_matching_rights_period_ftr_answer` | over_abstain | `null` | `3 business days` |
| contract_105 | `additional_matching_rights_period_for_modification` | over_abstain | `null` | `2 business days or less` |
| contract_105 | `number_of_additional_matching_rights_periods_for_m` | over_abstain | `null` | `Continuous matching right` |
| contract_105 | `acquisition_proposal_timing_answer` | wrong_value | `['Different Acquisition Proposal - Must sign durin` | `['Same Acquisition Proposal - Must sign during Tai` |
| contract_118 | `type_of_consideration_answer` | wrong_value | `Mixed Cash/Stock: Election` | `All Cash` |
| contract_118 | `accuracy_of_fundamental_target_rws_bringdown_stand` | wrong_value | `Accurate in all respects` | `Accurate at another materiality standard (e.g., hy` |
| contract_118 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['No MAE']` | `['Capitalization-Other', 'No MAE']` |
| contract_118 | `wnaf_subject_to_disproportionate_impact_answer` | wrong_value | `['Natural disaster', 'War or terrorism', 'force ma` | `['War or terrorism', '"act of God"', 'force majeur` |
| contract_118 | `includes_consistent_with_past_practice` | over_abstain | `null` | `Yes` |
| contract_118 | `limitations_on_ftr_exercise_answer` | wrong_value | `['Material breach of no-shop']` | `['Breach of no-shop resulting in a Superior Offer'` |
| contract_118 | `acquisition_proposal_timing_answer` | wrong_value | `['Different Acquisition Proposal - Must sign durin` | `['Same Acquisition Proposal - Must sign during Tai` |
| contract_118 | `breach_of_no_shop_required_to_be_willful_material_` | hallucination | `Yes` | `null` |
| contract_118 | `breach_of_meeting_covenant_required_to_be_willful_` | hallucination | `Yes` | `null` |
| contract_119 | `accuracy_of_fundamental_target_rws_types_of_rws` | over_abstain | `null` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_119 | `changes_in_targets_industry_yn` | wrong_value | `Yes` | `No` |
| contract_119 | `change_in_targets_industry_subject_to_disproportio` | wrong_value | `Yes` | `No` |
| contract_119 | `actions_taken_with_consent_or_approval_of_buyer_an` | wrong_value | `No` | `Yes` |
| contract_119 | `actions_taken_by_buyer_answer_yn` | wrong_value | `Yes` | `No` |
| contract_119 | `includes_consistent_with_past_practice` | wrong_value | `No` | `Yes` |
| contract_119 | `ordinary_course_efforts_standard_answer` | wrong_value | `Reasonable best efforts` | `Flat covenant (no efforts standard)` |
| contract_119 | `financial_point_of_view_is_the_sole_consideration` | hallucination | `No` | `null` |
| contract_119 | `acquisition_proposal_timing_answer` | wrong_value | `['Different Acquisition Proposal - Must sign durin` | `['Same Acquisition Proposal - Must sign during Tai` |
| contract_119 | `breach_of_no_shop_required_to_be_willful_material_` | hallucination | `Yes` | `null` |
| contract_121 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['Approval', 'Authority', "Brokers' Fee", 'Capital` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_121 | `materialitymae_scrape_applies_to` | hallucination | `['General R&Ws']` | `null` |
| contract_121 | `apc_application_to_answer` | wrong_value | `['announcement', 'consummation']` | `['announcement', 'pendency', 'consummation']` |
| contract_121 | `ordinary_course_efforts_standard_answer` | wrong_value | `Commercially reasonable efforts` | `Flat covenant (no efforts standard)` |
| contract_121 | `liability_standard_for_no_shop_breach_by_target_no` | wrong_value | `Strict liability` | `Reasonable standard` |
| contract_121 | `limitations_on_ftr_exercise_answer` | wrong_value | `['Any breach of no-shop']` | `['Breach of no-shop resulting in a Superior Offer'` |
| contract_121 | `acquisition_proposal_timing_answer` | wrong_value | `['Different Acquisition Proposal - Must sign durin` | `['Same Acquisition Proposal - Must sign during Tai` |
| … 82 more, see `analysis.json` … |||||
