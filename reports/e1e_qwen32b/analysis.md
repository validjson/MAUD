# E1 — Qwen 2.5 32B Instruct chunked baseline analysis

Per-contract per-field roll-up over **15 contracts** and **1380 single-choice + multilabel cells**.  Aggregate exact-match rate: **128/1380 = 9.3%**.

## Abstention / commit confusion

How the model's `null`/value choice lined up with gold's `null`/value:

|                          | gold = value | gold = null |
|--------------------------|-------------:|------------:|
| model = matching value  |    20 | — |
| model = mismatched val. |    21 | **2 hallucinations** |
| model = null            | **1229 over-abstentions** |   108 correct |

- **Correct-abstention rate** (cells where gold is null): 108/110 = 98.2%
- **Hallucination rate** (cells where gold is null, model committed): 2/110 = 1.8%
- **Commit rate** (cells where gold has a value): 41/1270 = 3.2%

## By field role

| Role | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|------|------:|--------:|-----:|--------------:|-------------:|------------:|
| single-choice | 1230 | 125 | 10.2% | 2 | 1085 | 18 |
| multilabel | 150 | 3 | 2.0% | 0 | 144 | 3 |

## Top-10 PCL-risk overlay

The paper's central claim is that fine-tuned models regress specifically on high-PCL-risk fields.  Prediction for E0a: a frontier reasoning model still mis-handles them, even without fine-tuning, because the failure mode lives in the input distribution rather than the training regime.

| Subset | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|--------|------:|--------:|-----:|--------------:|-------------:|------------:|
| Top-10 PCL-risk fields | 150 | 81 | **54.0%** | 2 | 67 | 0 |
| All other fields | 1230 | 47 | 3.8% | 0 | 1162 | 21 |

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
| a substituted enum value | 117 | 0 | 0.0% |
| a non-substituted value (same fields) | 78 | 31 | 39.7% |

A meaningful gap (e.g. >10pp) below the non-substituted rate is a methodological caveat worth recording in the case study.

## Per-field mismatches

All non-correct cells, up to 50 rows.  Full detail in `analysis.json` under `cells`.

| Contract | Field | Outcome | Pred | Gold |
|----------|-------|---------|------|------|
| contract_103 | `type_of_consideration_answer` | over_abstain | `null` | `All Cash` |
| contract_103 | `accuracy_of_target_general_rw_bringdown_timing_ans` | over_abstain | `null` | `At Closing Only` |
| contract_103 | `accuracy_of_target_general_rw_bringdown_standard_a` | over_abstain | `null` | `All/The R&Ws accurate at MAE standard` |
| contract_103 | `accuracy_of_target_capitalization_rw_outstanding_s` | over_abstain | `null` | `Accurate in all respects with de minimis exception` |
| contract_103 | `accuracy_of_fundamental_target_rws_bringdown_stand` | over_abstain | `null` | `Accurate in all material respects` |
| contract_103 | `accuracy_of_fundamental_target_rws_types_of_rws` | over_abstain | `null` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_103 | `materialitymae_scrape_applies_to` | over_abstain | `null` | `['General R&Ws']` |
| contract_103 | `compliance_with_target_covenant_closing_condition_` | over_abstain | `null` | `All Covenants` |
| contract_103 | `mae_definition_includes_adverse_impact_on_targets_` | over_abstain | `null` | `Yes` |
| contract_103 | `ability_to_consummate_concept_is_subject_to_mae_ca` | over_abstain | `null` | `No` |
| contract_103 | `mae_definition_includes_reference_to_target_prospe` | over_abstain | `null` | `No` |
| contract_103 | `mae_forward_looking_standard_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `fls_mae_applies_to` | over_abstain | `null` | `['ability to consummate transaction']` |
| contract_103 | `fls_mae_standard_answer` | over_abstain | `null` | `"Would"` |
| contract_103 | `mae_applies_to_target_and_subsidiaries_mae_answer` | over_abstain | `null` | `No` |
| contract_103 | `general_political_andor_social_conditions_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `general_political_andor_social_conditions_subject_` | over_abstain | `null` | `Yes` |
| contract_103 | `general_economic_and_financial_conditions_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `general_economic_and_financial_conditions_subject_` | over_abstain | `null` | `Yes` |
| contract_103 | `changes_in_targets_industry_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `change_in_targets_industry_subject_to_disproportio` | over_abstain | `null` | `Yes` |
| contract_103 | `change_in_law_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `change_in_law_subject_to_disproportionate_impact_m` | over_abstain | `null` | `Yes` |
| contract_103 | `changes_in_gaap_or_other_accounting_principles_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `changes_in_gaap_or_other_accounting_principles_sub` | over_abstain | `null` | `Yes` |
| contract_103 | `announcement_pendency_or_consummation_of_deal_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `apc_application_to_answer` | over_abstain | `null` | `['announcement']` |
| contract_103 | `failure_to_meet_projections_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `failure_to_meet_projections_subject_to_disproporti` | over_abstain | `null` | `No` |
| contract_103 | `changes_in_market_pricetrading_volume_of_targets_s` | over_abstain | `null` | `Yes` |
| contract_103 | `targets_securities_or_credit_rating_subject_to_dis` | over_abstain | `null` | `No` |
| contract_103 | `war_terrorism_natural_disasters_acts_of_god_or_for` | over_abstain | `null` | `Yes` |
| contract_103 | `wnaf_applies_to_answer` | over_abstain | `null` | `['War or terrorism', 'Natural disaster', '"act of ` |
| contract_103 | `wnaf_subject_to_disproportionate_impact_answer` | over_abstain | `null` | `['Natural disaster', '"act of God"']` |
| contract_103 | `pandemic_or_other_public_health_event_answer_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `pandemic_or_other_public_health_event_specific_ref` | over_abstain | `null` | `Yes` |
| contract_103 | `pandemic_or_other_public_health_event_specific_ref` | over_abstain | `null` | `Yes` |
| contract_103 | `pandemic_or_other_public_health_event_subject_to_d` | over_abstain | `null` | `Yes` |
| contract_103 | `actions_required_under_transaction_agreement_answe` | over_abstain | `null` | `No` |
| contract_103 | `actions_taken_with_consent_or_approval_of_buyer_an` | over_abstain | `null` | `Yes` |
| contract_103 | `target_stockholder_proceedings_answer_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `matters_listed_on_disclosure_schedules_answer_yn` | over_abstain | `null` | `No` |
| contract_103 | `actions_taken_by_buyer_answer_yn` | over_abstain | `null` | `No` |
| contract_103 | `action_prohibitedomission_required_by_the_agreemen` | over_abstain | `null` | `No` |
| contract_103 | `relational_language_mae_carveout_answer_yn` | over_abstain | `null` | `Yes` |
| contract_103 | `relational_language_mae_carveout_answer_dropdown` | over_abstain | `null` | `['"Resulting from"', '"Arising from/out of"', '"Re` |
| contract_103 | `relational_language_mae_applies_to` | over_abstain | `null` | `All MAE carveouts` |
| contract_103 | `knowledge_definition_answer` | over_abstain | `null` | `Actual knowledge` |
| contract_103 | `knowledge_definition_limited_to_one_or_more_identi` | over_abstain | `null` | `Yes` |
| contract_103 | `buyer_consent_requirement_ordinary_course_answer` | over_abstain | `null` | `Consent may not be unreasonably withheld, conditio` |
| … 1202 more, see `analysis.json` … |||||
