package handlers

import (
	"archive/zip"
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"pdf-toolkit/services"
)

func TestSplitRouteStreamsZipFolder(t *testing.T) {
	processor := &routeProcessor{pageCount: 4}
	handler := NewPDFHandler(services.NewPDFService(processor))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/split", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"groups": `[{"name":"DOC_A_rev1","pages":"1-2"},{"name":"DOC_B_rev1","pages":"3-4"}]`,
		"folder": "source split",
	})
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Type"); got != "application/zip" {
		t.Fatalf("Content-Type = %q", got)
	}
	if got := response.Header().Get("Content-Disposition"); got != `attachment; filename="source split.zip"` {
		t.Fatalf("Content-Disposition = %q", got)
	}

	body := response.Body.Bytes()
	archive, err := zip.NewReader(bytes.NewReader(body), int64(len(body)))
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"source split/DOC_A_rev1.pdf", "source split/DOC_B_rev1.pdf"}
	if len(archive.File) != len(want) {
		t.Fatalf("archive entries = %d, want %d", len(archive.File), len(want))
	}
	for index, entry := range archive.File {
		if entry.Name != want[index] {
			t.Fatalf("entry %d = %q, want %q", index, entry.Name, want[index])
		}
		reader, err := entry.Open()
		if err != nil {
			t.Fatal(err)
		}
		content, err := io.ReadAll(reader)
		_ = reader.Close()
		if err != nil || string(content) != "%PDF-1.7\nprocessed" {
			t.Fatalf("entry %q content = %q, err = %v", entry.Name, content, err)
		}
	}
}

func TestSplitRouteRejectsInvalidGroups(t *testing.T) {
	handler := NewPDFHandler(services.NewPDFService(&routeProcessor{pageCount: 2}))
	router := testRouter(handler)
	for _, groups := range []string{"[]", "not json", `[{"name":"a","pages":"3"}]`} {
		request := multipartRequest(t, "/api/v1/split", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
			"groups": groups,
		})
		response := httptest.NewRecorder()
		router.ServeHTTP(response, request)
		if response.Code != http.StatusBadRequest {
			t.Fatalf("groups %q: status = %d, want 400; body = %s", groups, response.Code, response.Body.String())
		}
	}
}
