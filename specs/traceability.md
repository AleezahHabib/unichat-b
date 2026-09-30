# UniChat Traceability Matrix

> *Note: This stub will be dynamically validated and maintained in Phase 8 via `scripts/trace.py`.*

| Acceptance Criteria ID | Feature Module | Specification File | Test Target | Status |
| :--- | :--- | :--- | :--- | :--- |
| **AC-01-01** | Authentication | `01-authentication/spec.md` | `test_auth_signup_validation` | Planned |
| **AC-01-02** | Authentication | `01-authentication/spec.md` | `test_auth_login_jwt` | Planned |
| **AC-01-03** | Authentication | `01-authentication/spec.md` | `test_auth_get_me` | Planned |
| **AC-01-04** | Authentication | `01-authentication/spec.md` | `test_auth_protected_routes` | Planned |
| **AC-02-01** | Workspaces & Channels | `02-workspaces-and-channels/spec.md` | `test_workspace_creation_default_general` | Planned |
| **AC-02-02** | Workspaces & Channels | `02-workspaces-and-channels/spec.md` | `test_workspace_invite_creation_and_expiry` | Planned |
| **AC-02-03** | Workspaces & Channels | `02-workspaces-and-channels/spec.md` | `test_workspace_invite_accept_idempotent` | Planned |
| **AC-02-04** | Workspaces & Channels | `02-workspaces-and-channels/spec.md` | `test_channel_crud_and_leave_rules` | Planned |
| **AC-02-05** | Workspaces & Channels | `02-workspaces-and-channels/spec.md` | `test_non_member_forbidden_403` | Planned |
| **AC-03-01** | Messaging | `03-messaging/spec.md` | `test_message_send_and_cursor_pagination` | Planned |
| **AC-03-02** | Messaging | `03-messaging/spec.md` | `test_message_edit_author_only` | Planned |
| **AC-03-03** | Messaging | `03-messaging/spec.md` | `test_message_soft_delete` | Planned |
| **AC-03-04** | Messaging | `03-messaging/spec.md` | `test_thread_replies_and_counts` | Planned |
| **AC-03-05** | Messaging | `03-messaging/spec.md` | `test_message_non_member_access` | Planned |
| **AC-03-06** | Messaging | `03-messaging/spec.md` | `test_message_rate_limit_429` | Planned |
| **AC-04-01** | Realtime | `04-realtime/spec.md` | `test_realtime_message_delivery_latency` | Planned |
| **AC-04-02** | Realtime | `04-realtime/spec.md` | `test_realtime_typing_indicator` | Planned |
| **AC-04-03** | Realtime | `04-realtime/spec.md` | `test_realtime_presence_lifecycle` | Planned |
| **AC-04-04** | Realtime | `04-realtime/spec.md` | `test_realtime_unauth_socket_timeout_4401` | Planned |
| **AC-04-05** | Realtime | `04-realtime/spec.md` | `test_realtime_workspace_event_isolation` | Planned |
| **AC-05-01** | Integrations | `05-integrations/spec.md` | `test_integration_token_encryption_and_perms` | Planned |
| **AC-05-02** | Integrations | `05-integrations/spec.md` | `test_channel_link_validation_1to1` | Planned |
| **AC-05-03** | Integrations | `05-integrations/spec.md` | `test_slack_inbound_sync` | Planned |
| **AC-05-04** | Integrations | `05-integrations/spec.md` | `test_discord_inbound_sync` | Planned |
| **AC-05-05** | Integrations | `05-integrations/spec.md` | `test_sync_duplicate_and_echo_prevention` | Planned |
| **AC-05-06** | Integrations | `05-integrations/spec.md` | `test_outbound_external_message_formatting` | Planned |
| **AC-05-07** | Integrations | `05-integrations/spec.md` | `test_slack_bidirectional_thread_mapping` | Planned |
| **AC-05-08** | Integrations | `05-integrations/spec.md` | `test_integration_disconnect_and_cleanup` | Planned |
| **AC-06-01** | AI Assistant | `06-ai-assistant/spec.md` | `test_ai_channel_summary_with_citations` | Planned |
| **AC-06-02** | AI Assistant | `06-ai-assistant/spec.md` | `test_ai_qa_citations_and_navigation` | Planned |
| **AC-06-03** | AI Assistant | `06-ai-assistant/spec.md` | `test_ai_draft_reply_to_composer` | Planned |
| **AC-06-04** | AI Assistant | `06-ai-assistant/spec.md` | `test_semantic_search_cross_platform` | Planned |
| **AC-06-05** | AI Assistant | `06-ai-assistant/spec.md` | `test_ai_rag_channel_membership_security` | Planned |
| **AC-06-06** | AI Assistant | `06-ai-assistant/spec.md` | `test_ai_error_handling_disabled_and_busy` | Planned |
| **AC-07-01** | Landing Page | `07-landing-page/spec.md` | `test_landing_page_render_and_auth_cta` | Planned |
| **AC-07-02** | Landing Page | `07-landing-page/spec.md` | `test_landing_hero_tabs_keyboard_nav` | Planned |
| **AC-07-03** | Landing Page | `07-landing-page/spec.md` | `test_landing_reduced_motion_static_frame` | Planned |
| **AC-07-04** | Landing Page | `07-landing-page/spec.md` | `test_landing_theme_toggle_persistence` | Planned |
| **AC-07-05** | Landing Page | `07-landing-page/spec.md` | `test_landing_lighthouse_performance` | Planned |
