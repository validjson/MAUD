# E1 — Qwen 2.5 32B Instruct chunked baseline analysis

Per-contract per-field roll-up over **15 contracts** and **1380 single-choice + multilabel cells**.  Aggregate exact-match rate: **777/1380 = 56.3%**.

## Abstention / commit confusion

How the model's `null`/value choice lined up with gold's `null`/value:

|                          | gold = value | gold = null |
|--------------------------|-------------:|------------:|
| model = matching value  |   772 | — |
| model = mismatched val. |   459 | **105 hallucinations** |
| model = null            | **39 over-abstentions** |     5 correct |

- **Correct-abstention rate** (cells where gold is null): 5/110 = 4.5%
- **Hallucination rate** (cells where gold is null, model committed): 105/110 = 95.5%
- **Commit rate** (cells where gold has a value): 1231/1270 = 96.9%

## By field role

| Role | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|------|------:|--------:|-----:|--------------:|-------------:|------------:|
| single-choice | 1230 | 736 | 59.8% | 102 | 39 | 353 |
| multilabel | 150 | 41 | 27.3% | 3 | 0 | 106 |

## Top-10 PCL-risk overlay

The paper's central claim is that fine-tuned models regress specifically on high-PCL-risk fields.  Prediction for E0a: a frontier reasoning model still mis-handles them, even without fine-tuning, because the failure mode lives in the input distribution rather than the training regime.

| Subset | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |
|--------|------:|--------:|-----:|--------------:|-------------:|------------:|
| Top-10 PCL-risk fields | 150 | 55 | **36.7%** | 79 | 5 | 11 |
| All other fields | 1230 | 722 | 58.7% | 26 | 34 | 448 |

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
| a substituted enum value | 117 | 16 | 13.7% |
| a non-substituted value (same fields) | 78 | 40 | 51.3% |

A meaningful gap (e.g. >10pp) below the non-substituted rate is a methodological caveat worth recording in the case study.

## Per-field mismatches

All non-correct cells, up to 50 rows.  Full detail in `analysis.json` under `cells`.

| Contract | Field | Outcome | Pred | Gold |
|----------|-------|---------|------|------|
| contract_103 | `accuracy_of_target_general_rw_bringdown_timing_ans` | wrong_value | `At Signing & At Closing` | `At Closing Only` |
| contract_103 | `accuracy_of_fundamental_target_rws_bringdown_stand` | wrong_value | `Accurate in all respects` | `Accurate in all material respects` |
| contract_103 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['Approval', 'Authority', "Brokers' Fee", 'Capital` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_103 | `materialitymae_scrape_applies_to` | wrong_value | `['Capitalization R&Ws', 'General R&Ws']` | `['General R&Ws']` |
| contract_103 | `absence_of_litigation_closing_condition_government` | hallucination | `Non-Governmental & governmental litigation` | `null` |
| contract_103 | `absence_of_litigation_closing_condition_pending_v_` | hallucination | `Pending` | `null` |
| contract_103 | `ability_to_consummate_concept_is_subject_to_mae_ca` | wrong_value | `Yes` | `No` |
| contract_103 | `mae_forward_looking_standard_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `fls_mae_applies_to` | wrong_value | `['ability to consummate transaction', 'business an` | `['ability to consummate transaction']` |
| contract_103 | `fls_mae_standard_answer` | wrong_value | `No` | `"Would"` |
| contract_103 | `wnaf_applies_to_answer` | wrong_value | `['Natural disaster', 'War or terrorism', 'force ma` | `['War or terrorism', 'Natural disaster', '"act of ` |
| contract_103 | `wnaf_subject_to_disproportionate_impact_answer` | wrong_value | `['Natural disaster', 'War or terrorism', 'force ma` | `['Natural disaster', '"act of God"']` |
| contract_103 | `pandemic_or_other_public_health_event_subject_to_d` | over_abstain | `null` | `Yes` |
| contract_103 | `actions_required_under_transaction_agreement_answe` | wrong_value | `Yes` | `No` |
| contract_103 | `target_stockholder_proceedings_answer_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `matters_listed_on_disclosure_schedules_answer_yn` | wrong_value | `Yes` | `No` |
| contract_103 | `action_prohibitedomission_required_by_the_agreemen` | wrong_value | `Yes` | `No` |
| contract_103 | `relational_language_mae_carveout_answer_yn` | wrong_value | `No` | `Yes` |
| contract_103 | `relational_language_mae_carveout_answer_dropdown` | wrong_value | `['"Resulting from"', 'Relational language varies a` | `['"Resulting from"', '"Arising from/out of"', '"Re` |
| contract_103 | `constructive_knowledge_answer` | hallucination | `Based on investigation or inquiry` | `null` |
| contract_103 | `ordinary_course_covenant_includes_carve_out_for_pa` | wrong_value | `No` | `Yes` |
| contract_103 | `negative_interim_covenant_includes_carveout_for_pa` | wrong_value | `No` | `Yes` |
| contract_103 | `general_antitrust_efforts_standard_answer` | wrong_value | `Commercially reasonable efforts` | `Reasonable best efforts` |
| contract_103 | `liability_standard_for_no_shop_breach_by_target_no` | wrong_value | `Strict liability` | `Reasonable standard` |
| contract_103 | `fiduciary_exception_board_determination_standard_a` | wrong_value | `None` | `"Reasonably likely/expected breach" of fiduciary d` |
| contract_103 | `fiduciary_exception_board_determination_trigger_no` | wrong_value | `Acquisition Proposal only` | `Superior Offer, or Acquisition Proposal reasonably` |
| contract_103 | `cor_permitted_with_board_fiduciary_determination_o` | wrong_value | `Yes` | `No` |
| contract_103 | `cor_standard_board_determination_only_answer` | hallucination | `More likely than not violate fiduciary duties` | `null` |
| contract_103 | `cor_standard_superior_offer` | wrong_value | `None` | `"Reasonably likely/expected breach" of fiduciary d` |
| contract_103 | `cor_standard_intervening_event` | wrong_value | `More likely than not violate fiduciary duties` | `"Reasonably likely/expected breach" of fiduciary d` |
| contract_103 | `initial_matching_rights_period_cor_answer` | wrong_value | `3 business days` | `5 business days` |
| contract_103 | `definition_includes_stock_deals_answer` | wrong_value | `50%` | `Greater than 50% but not "all or substantially all` |
| contract_103 | `definition_includes_asset_deals_answer` | wrong_value | `50%` | `Greater than 50% but not "all or substantially all` |
| contract_103 | `financial_point_of_view_is_the_sole_consideration` | wrong_value | `Yes` | `No` |
| contract_103 | `knowledge_persons_include_target_management_interv` | over_abstain | `null` | `No` |
| contract_103 | `intervening_event_required_to_occur_after_signing_` | wrong_value | `Must occur or arise after signing` | `May occur or arise prior to signing` |
| contract_103 | `limitations_on_ftr_exercise_answer` | wrong_value | `['Any breach of no-shop', 'Material breach of no-s` | `['Breach of no-shop resulting in a Superior Offer'` |
| contract_103 | `initial_matching_rights_period_ftr_answer` | wrong_value | `3 business days` | `5 business days` |
| contract_103 | `acquisition_proposal_required_to_be_publicly_discl` | wrong_value | `Yes` | `No` |
| contract_103 | `acquisition_proposal_required_to_be_publicly_discl` | wrong_value | `['“Publicly disclosed” requirement applies to Acqu` | `['No']` |
| contract_103 | `acquisition_proposal_required_to_be_still_pending_` | wrong_value | `Yes` | `No` |
| contract_103 | `breach_of_no_shop_required_to_be_willful_material_` | hallucination | `Yes` | `null` |
| contract_103 | `breach_of_meeting_covenant_required_to_be_willful_` | hallucination | `Yes` | `null` |
| contract_104 | `accuracy_of_target_general_rw_bringdown_timing_ans` | wrong_value | `At Signing & At Closing` | `At Closing Only` |
| contract_104 | `accuracy_of_target_capitalization_rw_outstanding_s` | wrong_value | `Accurate in all respects` | `Accurate in all respects with de minimis exception` |
| contract_104 | `accuracy_of_fundamental_target_rws_bringdown_stand` | wrong_value | `Accurate in all respects` | `Accurate in all material respects` |
| contract_104 | `accuracy_of_fundamental_target_rws_types_of_rws` | wrong_value | `['Approval', 'Authority', "Brokers' Fee", 'Capital` | `['Capitalization-Other', 'Authority', 'Approval', ` |
| contract_104 | `materialitymae_scrape_applies_to` | wrong_value | `['Capitalization R&Ws', 'General R&Ws', 'fundament` | `['General R&Ws']` |
| contract_104 | `absence_of_litigation_closing_condition_government` | hallucination | `Non-Governmental & governmental litigation` | `null` |
| contract_104 | `absence_of_litigation_closing_condition_pending_v_` | hallucination | `Pending` | `null` |
| … 553 more, see `analysis.json` … |||||
