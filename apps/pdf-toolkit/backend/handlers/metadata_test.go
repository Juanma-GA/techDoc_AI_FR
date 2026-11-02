package handlers

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"pdf-toolkit/services"
)

func TestEditMetadataRouteStreamsPDFAndCleansWorkspace(t *testing.T) {
	processor := &routeProcessor{}
	request := multipartRequest(t, "/api/v1/edit-metadata", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"title": "Titre", "author": "Auteur", "subject": "", "keywords": "one, two",
	})
	response := httptest.NewRecorder()
	testRouter(NewPDFHandler(services.NewPDFService(processor))).ServeHTTP(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=metadata.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if response.Header().Get("Cache-Control") != "no-store" || response.Body.String() != "%PDF-1.7\nprocessed" {
		t.Fatal("missing PDF output or cache prevention")
	}
	want := services.PDFMetadata{Title: "Titre", Author: "Auteur", Keywords: "one, two"}
	if processor.metadata != want {
		t.Fatalf("metadata = %+v, want %+v", processor.metadata, want)
	}
	if _, err := os.Stat(processor.inputPath); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("temporary input still exists: %v", err)
	}
}

func TestEditMetadataRouteRejectsMissingFieldsAndInvalidPDF(t *testing.T) {
	for _, field := range []string{"title", "author", "subject", "keywords"} {
		fields := map[string]string{"title": "", "author": "", "subject": "", "keywords": ""}
		delete(fields, field)
		response := httptest.NewRecorder()
		request := multipartRequest(t, "/api/v1/edit-metadata", "file", "source.pdf", "%PDF-1.7\ninput", fields)
		testRouter(NewPDFHandler(services.NewPDFService(&routeProcessor{}))).ServeHTTP(response, request)
		if response.Code != http.StatusBadRequest {
			t.Fatalf("missing %s: status = %d", field, response.Code)
		}
	}
	processor := &routeProcessor{metadataErr: errors.New("invalid PDF")}
	request := multipartRequest(t, "/api/v1/edit-metadata", "file", "broken.pdf", "%PDF-1.7\nbroken", map[string]string{
		"title": "", "author": "", "subject": "", "keywords": "",
	})
	response := httptest.NewRecorder()
	testRouter(NewPDFHandler(services.NewPDFService(processor))).ServeHTTP(response, request)
	if response.Code != http.StatusUnprocessableEntity {
		t.Fatalf("invalid PDF: status = %d", response.Code)
	}
	if _, err := os.Stat(processor.inputPath); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("temporary input still exists after failure: %v", err)
	}
}
