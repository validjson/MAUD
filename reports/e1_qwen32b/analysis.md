# E1 — Qwen 2.5 32B Instruct chunked baseline analysis

Per-contract per-field roll-up over **15 contracts** and **1380 single-choice + multilabel cells**.  Aggregate exact-match rate: **422/1380 = 30.6%**.

## Abstention / commit confusion

How the model's `null`/value choice lined up with gold's `null`/value:

|                          | gold = value | gold = null |
|--------------------------|-------------:|------------:|
| model = matching value  |   372 | — |
| model = mismatched val. |   474 | **60 hallucinations** |
| model = null            | **424 over-abstentions** |    50 correct |

- **Correct-abstention rate** (cells where gold is null): 50/110 = 45.5%
- **Hallucination rate** (cells where gold is null, model committed): 60/110 = 54.5%
- **Commit rate** (cells where gold has a value): 846/1270 = 66.6%

## By field role

| Role | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|------|------:|--------:|-----:|--------------:|-------------:|------------:|
| single-choice | 1230 | 405 | 32.9% | 58 | 394 | 373 |
| multilabel | 150 | 17 | 11.3% | 2 | 30 | 101 |

## Top-10 PCL-risk overlay

The paper's central claim is that fine-tuned models regress specifically on high-PCL-risk fields.  Prediction for E0a: a frontier reasoning model still mis-handles them, even without fine-tuning, because the failure mode lives in the input distribution rather than the training regime.

| Subset | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|--------|------:|--------:|-----:|--------------:|-------------:|------------:|
| Top-10 PCL-risk fields | 150 | 53 | **35.3%** | 48 | 27 | 22 |
| All other fields | 1230 | 369 | 30.0% | 12 | 397 | 452 |

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
| a substituted enum value | 117 | 8 | 6.8% |
| a non-substituted value (same fields) | 78 | 33 | 42.3% |

A meaningful gap (e.g. >10pp) below the non-substituted rate is a methodological caveat worth recording in the case study.

## Per-field mismatches

All non-correct cells, up to 50 rows.  Full detail in `analysis.json` under `cells`.

| Contract | Field | Outcome | Pred | Gold |
|----------|-------|---------|------|------|
| contract_103 | `accuracy_of_target_general_rw_bringdown_timing_ans` | over_abstain | `null` | `At Closing Only` |
| contract_103 | `accuracy_of_target_general_rw_bringdown_standard_a` | over_abstain | `null` | `All/The R&Ws accurate at MAE standard` |
| contract_103 | `accuracy_of_target_capitalization_rw_outstanding_s` | over_abstain | `null` | `Accurate in all respects with de minimis exception` |
| contract_103 | `accuracy_of_fundamental_target_rws_bringdown_stand` | over_abstain | `null` | `Accurate in all material respects` |
| contract_103 | `accuracy_of_fundamental_target_rws_types_of_rws` | over_abstain | `null` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_103 | `materialitymae_scrape_applies_to` | wrong_value | `['Capitalization R&Ws']` | `['General R&Ws']` |
| contract_103 | `compliance_with_target_covenant_closing_condition_` | over_abstain | `null` | `All Covenants` |
| contract_103 | `ability_to_consummate_concept_is_subject_to_mae_ca` | over_abstain | `null` | `No` |
| contract_103 | `mae_definition_includes_reference_to_target_prospe` | wrong_value | `Yes` | `No` |
| contract_103 | `mae_forward_looking_standard_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `fls_mae_standard_answer` | wrong_value | `"Would" (reasonably) be expected to` | `"Would"` |
| contract_103 | `mae_applies_to_target_and_subsidiaries_mae_answer` | over_abstain | `null` | `No` |
| contract_103 | `general_political_andor_social_conditions_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `general_political_andor_social_conditions_subject_` | wrong_value | `No` | `Yes` |
| contract_103 | `general_economic_and_financial_conditions_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `general_economic_and_financial_conditions_subject_` | wrong_value | `No` | `Yes` |
| contract_103 | `changes_in_targets_industry_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `change_in_targets_industry_subject_to_disproportio` | wrong_value | `No` | `Yes` |
| contract_103 | `change_in_law_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `change_in_law_subject_to_disproportionate_impact_m` | wrong_value | `No` | `Yes` |
| contract_103 | `changes_in_gaap_or_other_accounting_principles_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `changes_in_gaap_or_other_accounting_principles_sub` | wrong_value | `No` | `Yes` |
| contract_103 | `announcement_pendency_or_consummation_of_deal_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `failure_to_meet_projections_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `changes_in_market_pricetrading_volume_of_targets_s` | wrong_value | `No` | `Yes` |
| contract_103 | `war_terrorism_natural_disasters_acts_of_god_or_for` | wrong_value | `No` | `Yes` |
| contract_103 | `wnaf_applies_to_answer` | wrong_value | `['Natural disaster', 'War or terrorism']` | `['War or terrorism', 'Natural disaster', '"act of ` |
| contract_103 | `wnaf_subject_to_disproportionate_impact_answer` | wrong_value | `['Natural disaster', 'War or terrorism']` | `['Natural disaster', '"act of God"']` |
| contract_103 | `pandemic_or_other_public_health_event_specific_ref` | wrong_value | `No` | `Yes` |
| contract_103 | `pandemic_or_other_public_health_event_specific_ref` | wrong_value | `No` | `Yes` |
| contract_103 | `pandemic_or_other_public_health_event_subject_to_d` | wrong_value | `No` | `Yes` |
| contract_103 | `actions_taken_with_consent_or_approval_of_buyer_an` | wrong_value | `No` | `Yes` |
| contract_103 | `target_stockholder_proceedings_answer_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `relational_language_mae_carveout_answer_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `relational_language_mae_carveout_answer_dropdown` | over_abstain | `null` | `['"Resulting from"', '"Arising from/out of"', '"Re` |
| contract_103 | `relational_language_mae_applies_to` | wrong_value | `No` | `All MAE carveouts` |
| contract_103 | `buyer_consent_requirement_ordinary_course_answer` | over_abstain | `null` | `Consent may not be unreasonably withheld, conditio` |
| contract_103 | `ordinary_course_efforts_standard_answer` | over_abstain | `null` | `Flat covenant (no efforts standard)` |
| contract_103 | `ordinary_course_covenant_includes_carve_out_for_pa` | wrong_value | `No` | `Yes` |
| contract_103 | `buyer_consent_requirement_negative_interim_covenan` | over_abstain | `null` | `Consent may not be unreasonably withheld, conditio` |
| contract_103 | `application_of_buyer_consent_requirement_negative_` | over_abstain | `null` | `Applies to all negative covenants` |
| contract_103 | `negative_interim_covenant_includes_carveout_for_pa` | wrong_value | `No` | `Yes` |
| contract_103 | `general_antitrust_efforts_standard_answer` | over_abstain | `null` | `Reasonable best efforts` |
| contract_103 | `liability_for_breaches_of_no_shop_by_target_repres` | wrong_value | `No` | `Yes` |
| contract_103 | `liability_standard_for_no_shop_breach_by_target_no` | over_abstain | `null` | `Reasonable standard` |
| contract_103 | `fiduciary_exception_board_determination_standard_a` | over_abstain | `null` | `"Reasonably likely/expected breach" of fiduciary d` |
| contract_103 | `fiduciary_exception_board_determination_trigger_no` | over_abstain | `null` | `Superior Offer, or Acquisition Proposal reasonably` |
| contract_103 | `cor_permitted_with_board_fiduciary_determination_o` | over_abstain | `null` | `No` |
| contract_103 | `cor_standard_superior_offer` | over_abstain | `null` | `"Reasonably likely/expected breach" of fiduciary d` |
| contract_103 | `cor_permitted_in_response_to_intervening_event` | over_abstain | `null` | `Yes` |
| … 908 more, see `analysis.json` … |||||
