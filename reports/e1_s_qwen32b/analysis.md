# E1 — Qwen 2.5 32B Instruct chunked baseline analysis

Per-contract per-field roll-up over **15 contracts** and **1380 single-choice + multilabel cells**.  Aggregate exact-match rate: **453/1380 = 32.8%**.

## Abstention / commit confusion

How the model's `null`/value choice lined up with gold's `null`/value:

|                          | gold = value | gold = null |
|--------------------------|-------------:|------------:|
| model = matching value  |   396 | — |
| model = mismatched val. |   381 | **53 hallucinations** |
| model = null            | **493 over-abstentions** |    57 correct |

- **Correct-abstention rate** (cells where gold is null): 57/110 = 51.8%
- **Hallucination rate** (cells where gold is null, model committed): 53/110 = 48.2%
- **Commit rate** (cells where gold has a value): 777/1270 = 61.2%

## By field role

| Role | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|------|------:|--------:|-----:|--------------:|-------------:|------------:|
| single-choice | 1230 | 448 | 36.4% | 52 | 392 | 338 |
| multilabel | 150 | 5 | 3.3% | 1 | 101 | 43 |

## Top-10 PCL-risk overlay

The paper's central claim is that fine-tuned models regress specifically on high-PCL-risk fields.  Prediction for E0a: a frontier reasoning model still mis-handles them, even without fine-tuning, because the failure mode lives in the input distribution rather than the training regime.

| Subset | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|--------|------:|--------:|-----:|--------------:|-------------:|------------:|
| Top-10 PCL-risk fields | 150 | 49 | **32.7%** | 48 | 39 | 14 |
| All other fields | 1230 | 404 | 32.8% | 5 | 454 | 367 |

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
| a non-substituted value (same fields) | 78 | 30 | 38.5% |

A meaningful gap (e.g. >10pp) below the non-substituted rate is a methodological caveat worth recording in the case study.

## Per-field mismatches

All non-correct cells, up to 50 rows.  Full detail in `analysis.json` under `cells`.

| Contract | Field | Outcome | Pred | Gold |
|----------|-------|---------|------|------|
| contract_103 | `type_of_consideration_answer` | wrong_value | `Mixed Cash/Stock` | `All Cash` |
| contract_103 | `accuracy_of_target_general_rw_bringdown_standard_a` | wrong_value | `All/The R&Ws accurate in all respects (repeating R` | `All/The R&Ws accurate at MAE standard` |
| contract_103 | `accuracy_of_target_capitalization_rw_outstanding_s` | wrong_value | `Accurate in all material respects` | `Accurate in all respects with de minimis exception` |
| contract_103 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['No MAE']` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_103 | `materialitymae_scrape_applies_to` | wrong_value | `['Capitalization R&Ws', 'Specified R&Ws only']` | `['General R&Ws']` |
| contract_103 | `absence_of_litigation_closing_condition_government` | hallucination | `Non-Governmental & governmental litigation` | `null` |
| contract_103 | `absence_of_litigation_closing_condition_pending_v_` | hallucination | `Pending` | `null` |
| contract_103 | `mae_definition_includes_reference_to_target_prospe` | wrong_value | `Yes` | `No` |
| contract_103 | `fls_mae_applies_to` | wrong_value | `['No']` | `['ability to consummate transaction']` |
| contract_103 | `fls_mae_standard_answer` | wrong_value | `No` | `"Would"` |
| contract_103 | `general_political_andor_social_conditions_subject_` | wrong_value | `No` | `Yes` |
| contract_103 | `general_economic_and_financial_conditions_subject_` | wrong_value | `No` | `Yes` |
| contract_103 | `change_in_targets_industry_subject_to_disproportio` | wrong_value | `No` | `Yes` |
| contract_103 | `change_in_law_subject_to_disproportionate_impact_m` | wrong_value | `No` | `Yes` |
| contract_103 | `changes_in_gaap_or_other_accounting_principles_sub` | wrong_value | `No` | `Yes` |
| contract_103 | `apc_application_to_answer` | over_abstain | `null` | `['announcement']` |
| contract_103 | `wnaf_applies_to_answer` | over_abstain | `null` | `['War or terrorism', 'Natural disaster', '"act of ` |
| contract_103 | `wnaf_subject_to_disproportionate_impact_answer` | over_abstain | `null` | `['Natural disaster', '"act of God"']` |
| contract_103 | `pandemic_or_other_public_health_event_specific_ref` | wrong_value | `No` | `Yes` |
| contract_103 | `pandemic_or_other_public_health_event_specific_ref` | wrong_value | `No` | `Yes` |
| contract_103 | `pandemic_or_other_public_health_event_subject_to_d` | wrong_value | `No` | `Yes` |
| contract_103 | `actions_required_under_transaction_agreement_answe` | wrong_value | `Yes` | `No` |
| contract_103 | `matters_listed_on_disclosure_schedules_answer_yn` | wrong_value | `Yes` | `No` |
| contract_103 | `actions_taken_by_buyer_answer_yn` | wrong_value | `Yes` | `No` |
| contract_103 | `action_prohibitedomission_required_by_the_agreemen` | over_abstain | `null` | `No` |
| contract_103 | `relational_language_mae_carveout_answer_dropdown` | wrong_value | `['No']` | `['"Resulting from"', '"Arising from/out of"', '"Re` |
| contract_103 | `relational_language_mae_applies_to` | over_abstain | `null` | `All MAE carveouts` |
| contract_103 | `knowledge_definition_answer` | over_abstain | `null` | `Actual knowledge` |
| contract_103 | `buyer_consent_requirement_ordinary_course_answer` | over_abstain | `null` | `Consent may not be unreasonably withheld, conditio` |
| contract_103 | `includes_consistent_with_past_practice` | wrong_value | `No` | `Yes` |
| contract_103 | `ordinary_course_efforts_standard_answer` | over_abstain | `null` | `Flat covenant (no efforts standard)` |
| contract_103 | `buyer_consent_requirement_negative_interim_covenan` | over_abstain | `null` | `Consent may not be unreasonably withheld, conditio` |
| contract_103 | `application_of_buyer_consent_requirement_negative_` | over_abstain | `null` | `Applies to all negative covenants` |
| contract_103 | `general_antitrust_efforts_standard_answer` | over_abstain | `null` | `Reasonable best efforts` |
| contract_103 | `liability_standard_for_no_shop_breach_by_target_no` | wrong_value | `Strict liability` | `Reasonable standard` |
| contract_103 | `fiduciary_exception_board_determination_standard_a` | wrong_value | `None` | `"Reasonably likely/expected breach" of fiduciary d` |
| contract_103 | `fiduciary_exception_board_determination_trigger_no` | over_abstain | `null` | `Superior Offer, or Acquisition Proposal reasonably` |
| contract_103 | `cor_standard_superior_offer` | wrong_value | `None` | `"Reasonably likely/expected breach" of fiduciary d` |
| contract_103 | `cor_permitted_in_response_to_intervening_event` | wrong_value | `No` | `Yes` |
| contract_103 | `cor_standard_intervening_event` | wrong_value | `More likely than not violate fiduciary duties` | `"Reasonably likely/expected breach" of fiduciary d` |
| contract_103 | `initial_matching_rights_period_cor_answer` | over_abstain | `null` | `5 business days` |
| contract_103 | `additional_matching_rights_period_for_modification` | over_abstain | `null` | `2 business days or less` |
| contract_103 | `number_of_additional_matching_rights_periods_for_m` | wrong_value | `None` | `Continuous matching right` |
| contract_103 | `definition_includes_stock_deals_answer` | over_abstain | `null` | `Greater than 50% but not "all or substantially all` |
| contract_103 | `definition_includes_asset_deals_answer` | over_abstain | `null` | `Greater than 50% but not "all or substantially all` |
| contract_103 | `definition_contains_knowledge_requirement_answer` | over_abstain | `null` | `Not known at signing` |
| contract_103 | `intervening_event_required_to_occur_after_signing_` | over_abstain | `null` | `May occur or arise prior to signing` |
| contract_103 | `ftr_triggers_answer` | over_abstain | `null` | `Superior Offer` |
| contract_103 | `limitations_on_ftr_exercise_answer` | over_abstain | `null` | `['Breach of no-shop resulting in a Superior Offer'` |
| contract_103 | `initial_matching_rights_period_ftr_answer` | over_abstain | `null` | `5 business days` |
| … 877 more, see `analysis.json` … |||||
