from unittest.mock import MagicMock, patch

import pytest

from me3_manager.services.nexus_service import NexusForbiddenError, NexusService


def test_get_download_links_preserves_nexus_forbidden_error():
    service = NexusService(api_key="test_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {
        "message": "You don't have permission to get download links from the API without visting nexusmods.com - this is for premium users only."
    }

    with patch.object(service._session, "request", return_value=mock_resp):
        with pytest.raises(NexusForbiddenError) as exc_info:
            service.get_download_links("eldenring", 123, 456)

        assert "premium users only" in str(exc_info.value)
