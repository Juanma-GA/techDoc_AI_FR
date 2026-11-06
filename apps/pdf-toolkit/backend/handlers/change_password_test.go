package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"pdf-toolkit/services"
)

func TestChangePasswordRouteStreamsUpdatedPDF(t *testing.T) {
	handler := NewPDFHandler(services.NewPDFService(&routeProcessor{}))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/change-password", "file", "protected.pdf", "%PDF-1.7\ninput", map[string]string{
		"owner_password":    "owner-password",
		"new_user_password": "new-open-password",
	})
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=password-updated.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if response.Body.String() != "%PDF-1.7\nprocessed" {
		t.Fatalf("response body = %q", response.Body.String())
	}
}
