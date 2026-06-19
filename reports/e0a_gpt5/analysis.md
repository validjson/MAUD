# E0a — GPT-5.5 baseline analysis

Per-contract per-field roll-up over **15 contracts** and **1380 single-choice + multilabel cells**.  Aggregate exact-match rate: **1251/1380 = 90.7%**.

## Abstention / commit confusion

How the model's `null`/value choice lined up with gold's `null`/value:

|                          | gold = value | gold = null |
|--------------------------|-------------:|------------:|
| model = matching value  |  1178 | — |
| model = mismatched val. |    88 | **37 hallucinations** |
| model = null            | **4 over-abstentions** |    73 correct |

- **Correct-abstention rate** (cells where gold is null): 73/110 = 66.4%
- **Hallucination rate** (cells where gold is null, model committed): 37/110 = 33.6%
- **Commit rate** (cells where gold has a value): 1266/1270 = 99.7%

## By field role

| Role | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|------|------:|--------:|-----:|--------------:|-------------:|------------:|
| single-choice | 1230 | 1143 | 92.9% | 36 | 4 | 47 |
| multilabel | 150 | 108 | 72.0% | 1 | 0 | 41 |

## Top-10 PCL-risk overlay

The paper's central claim is that fine-tuned models regress specifically on high-PCL-risk fields.  Prediction for E0a: a frontier reasoning model still mis-handles them, even without fine-tuning, because the failure mode lives in the input distribution rather than the training regime.

| Subset | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|--------|------:|--------:|-----:|--------------:|-------------:|------------:|
| Top-10 PCL-risk fields | 150 | 112 | **74.7%** | 36 | 0 | 2 |
| All other fields | 1230 | 1139 | 92.6% | 1 | 4 | 86 |

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
| a substituted enum value | 117 | 111 | 94.9% |
| a non-substituted value (same fields) | 78 | 60 | 76.9% |

A meaningful gap (e.g. >10pp) below the non-substituted rate is a methodological caveat worth recording in the case study.

## Per-field mismatches

All non-correct cells, up to 50 rows.  Full detail in `analysis.json` under `cells`.

| Contract | Field | Outcome | Pred | Gold |
|----------|-------|---------|------|------|
| contract_103 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['Organization', 'Subsidiaries', 'Capitalization-O` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_103 | `absence_of_litigation_closing_condition_government` | hallucination | `Governmental litigation only` | `null` |
| contract_103 | `absence_of_litigation_closing_condition_pending_v_` | hallucination | `Pending` | `null` |
| contract_103 | `fls_mae_applies_to` | wrong_value | `['ability to consummate transaction', 'business an` | `['ability to consummate transaction']` |
| contract_103 | `fls_mae_standard_answer` | wrong_value | `"Would" (reasonably) be expected to` | `"Would"` |
| contract_103 | `mae_applies_to_target_and_subsidiaries_mae_answer` | wrong_value | `Applies to Target and subsidiaries "taken as a who` | `No` |
| contract_103 | `general_political_andor_social_conditions_subject_` | wrong_value | `No` | `Yes` |
| contract_103 | `actions_required_under_transaction_agreement_answe` | wrong_value | `Yes` | `No` |
| contract_103 | `liability_standard_for_no_shop_breach_by_target_no` | wrong_value | `Strict liability` | `Reasonable standard` |
| contract_103 | `acquisition_proposal_timing_answer` | wrong_value | `['Different Acquisition Proposal - Must sign durin` | `['Same Acquisition Proposal - Must sign during Tai` |
| contract_103 | `breach_of_no_shop_required_to_be_willful_material_` | hallucination | `No` | `null` |
| contract_104 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['Organization', 'Authority', 'Approval', 'Enforce` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_104 | `absence_of_litigation_closing_condition_government` | hallucination | `Governmental litigation only` | `null` |
| contract_104 | `absence_of_litigation_closing_condition_pending_v_` | hallucination | `Pending` | `null` |
| contract_104 | `fls_mae_applies_to` | wrong_value | `['business and operation of Target', 'ability to c` | `['business and operation of Target']` |
| contract_104 | `apc_application_to_answer` | wrong_value | `['announcement', 'consummation']` | `['announcement', 'pendency', 'consummation']` |
| contract_104 | `fiduciary_exception_board_determination_standard_a` | wrong_value | `"Inconsistent" with fiduciary duties` | `"Reasonably likely/expected to be inconsistent" wi` |
| contract_104 | `financial_point_of_view_is_the_sole_consideration` | wrong_value | `Yes` | `No` |
| contract_104 | `acquisition_proposal_timing_answer` | wrong_value | `['Same Acquisition Proposal - Must close during Ta` | `['Same Acquisition Proposal - Must sign during Tai` |
| contract_104 | `breach_of_no_shop_required_to_be_willful_material_` | hallucination | `No` | `null` |
| contract_105 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['Approval', 'Authority', "Brokers' Fee", 'Capital` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_105 | `pandemic_or_other_public_health_event_subject_to_d` | wrong_value | `Yes` | `No` |
| contract_105 | `fiduciary_exception_board_determination_standard_a` | wrong_value | `"Inconsistent" with fiduciary duties` | `None` |
| contract_105 | `acquisition_proposal_timing_answer` | wrong_value | `['Different Acquisition Proposal - Must sign durin` | `['Same Acquisition Proposal - Must sign during Tai` |
| contract_105 | `breach_of_no_shop_required_to_be_willful_material_` | hallucination | `No` | `null` |
| contract_105 | `breach_of_meeting_covenant_required_to_be_willful_` | hallucination | `No` | `null` |
| contract_118 | `absence_of_litigation_closing_condition_government` | hallucination | `Governmental litigation only` | `null` |
| contract_118 | `absence_of_litigation_closing_condition_pending_v_` | hallucination | `Pending` | `null` |
| contract_118 | `wnaf_subject_to_disproportionate_impact_answer` | wrong_value | `['Natural disaster', 'War or terrorism', 'force ma` | `['War or terrorism', '"act of God"', 'force majeur` |
| contract_118 | `relational_language_mae_carveout_answer_dropdown` | wrong_value | `['"Arising from/out of"', '"Relating to"', '"Resul` | `['"Resulting from"']` |
| contract_118 | `negative_interim_covenant_includes_carveout_for_pa` | wrong_value | `Yes` | `No` |
| contract_118 | `limitations_on_ftr_exercise_answer` | wrong_value | `['Breach of no-shop resulting in a Superior Offer'` | `['Breach of no-shop resulting in a Superior Offer'` |
| contract_118 | `acquisition_proposal_timing_answer` | wrong_value | `['Different Acquisition Proposal - Must sign durin` | `['Same Acquisition Proposal - Must sign during Tai` |
| contract_118 | `breach_of_no_shop_required_to_be_willful_material_` | hallucination | `Yes` | `null` |
| contract_118 | `breach_of_meeting_covenant_required_to_be_willful_` | hallucination | `Yes` | `null` |
| contract_119 | `absence_of_litigation_closing_condition_government` | hallucination | `Governmental litigation only` | `null` |
| contract_119 | `absence_of_litigation_closing_condition_pending_v_` | hallucination | `Pending` | `null` |
| contract_119 | `changes_in_targets_industry_yn` | wrong_value | `Yes` | `No` |
| contract_119 | `change_in_targets_industry_subject_to_disproportio` | wrong_value | `Yes` | `No` |
| contract_119 | `actions_taken_with_consent_or_approval_of_buyer_an` | wrong_value | `No` | `Yes` |
| contract_119 | `actions_taken_by_buyer_answer_yn` | wrong_value | `Yes` | `No` |
| contract_119 | `liability_standard_for_no_shop_breach_by_target_no` | wrong_value | `Reasonable standard` | `Strict liability` |
| contract_119 | `definition_includes_stock_deals_answer` | wrong_value | `50%` | `Greater than 50% but not "all or substantially all` |
| contract_119 | `financial_point_of_view_is_the_sole_consideration` | hallucination | `No` | `null` |
| contract_119 | `acquisition_proposal_timing_answer` | wrong_value | `['Same Acquisition Proposal - Must sign during Tai` | `['Same Acquisition Proposal - Must sign during Tai` |
| contract_119 | `breach_of_no_shop_required_to_be_willful_material_` | hallucination | `Yes` | `null` |
| contract_121 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['Organization', 'Subsidiaries', 'Capitalization-O` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_121 | `materialitymae_scrape_applies_to` | hallucination | `['General R&Ws']` | `null` |
| contract_121 | `absence_of_litigation_closing_condition_government` | hallucination | `Governmental litigation only` | `null` |
| contract_121 | `absence_of_litigation_closing_condition_pending_v_` | hallucination | `Pending` | `null` |
| … 79 more, see `analysis.json` … |||||
