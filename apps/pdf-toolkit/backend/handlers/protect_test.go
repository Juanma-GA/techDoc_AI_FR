package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"pdf-toolkit/services"
)

func TestProtectRouteStreamsProtectedPDF(t *testing.T) {
	processor := &routeProcessor{}
	handler := NewPDFHandler(services.NewPDFService(processor))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/protect", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"user_password":   "user-password",
		"owner_password":  "owner-password",
		"allow_print":     "true",
		"allow_copy":      "false",
		"allow_modify":    "false",
		"allow_comments":  "true",
		"allow_form_fill": "true",
		"allow_sign":      "true",
	})
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=protected.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if response.Body.String() != "%PDF-1.7\nprocessed" {
		t.Fatalf("response body = %q", response.Body.String())
	}
	if !processor.protected.AllowPrint ||
		processor.protected.AllowCopy ||
		processor.protected.AllowModify ||
		!processor.protected.AllowComments ||
		!processor.protected.AllowFormFill ||
		!processor.protected.AllowSign {
		t.Fatalf("protection options = %+v, want comments, form fill, and signing enabled", processor.protected)
	}
}

func TestProtectRouteRejectsMissingPasswordFields(t *testing.T) {
	handler := NewPDFHandler(services.NewPDFService(&routeProcessor{}))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/protect", "file", "source.pdf", "%PDF-1.7\ninput", nil)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusBadRequest)
	}
}
