package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"pdf-toolkit/services"
)

func (p *routeProcessor) AddComments(
	_ context.Context,
	input, output string,
	comments []services.PDFComment,
) error {
	p.inputPath = input
	p.comments = append([]services.PDFComment(nil), comments...)
	return writeRoutePDF(output)
}

func TestCommentsRouteAddsPDFAnnotationsAndCleansWorkspace(t *testing.T) {
	processor := &routeProcessor{pageCount: 3}
	comments := []services.PDFComment{
		{Page: 2, X: 123, Y: 456, Content: "À vérifier"},
	}
	rawComments, err := json.Marshal(comments)
	if err != nil {
		t.Fatal(err)
	}
	request := multipartRequest(t, "/api/v1/comments", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"comments": string(rawComments),
	})
	response := httptest.NewRecorder()
	testRouter(NewPDFHandler(services.NewPDFService(processor))).ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=commented.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if response.Body.String() != "%PDF-1.7\nprocessed" {
		t.Fatalf("response body = %q", response.Body.String())
	}
	if len(processor.comments) != 1 || processor.comments[0] != comments[0] {
		t.Fatalf("comments = %+v, want %+v", processor.comments, comments)
	}
	if _, err := os.Stat(processor.inputPath); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("temporary PDF still exists after response: %v", err)
	}
}

func TestCommentsRouteRejectsInvalidCommentJSON(t *testing.T) {
	request := multipartRequest(t, "/api/v1/comments", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"comments": "[",
	})
	response := httptest.NewRecorder()
	testRouter(NewPDFHandler(services.NewPDFService(&routeProcessor{pageCount: 1}))).ServeHTTP(response, request)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusBadRequest)
	}
}
