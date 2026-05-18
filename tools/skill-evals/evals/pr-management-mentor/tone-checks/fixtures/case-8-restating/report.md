@henry — If I understand correctly, you're saying the tests are failing
because the fixture data doesn't match the new schema.

Run `pytest tests/providers/http/ -x` to confirm, then update the
fixtures to reflect the new field names.

<ai_attribution_footer>
