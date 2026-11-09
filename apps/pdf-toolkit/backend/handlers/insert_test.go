package handlers

import (
	"bytes"
	"errors"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
	"testing"

	"pdf-toolkit/services"
)

func insertRequest(t *testing.T, files int, fields map[string]string) *http.Request {
	t.Helper()
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	for name, value := range fields {
		if err := form.WriteField(name, value); err != nil {
			t.Fatal(err)
		}
	}
	for index := 0; index < files; index++ {
		part, err := form.CreateFormFile("files", []string{"target.pdf", "source.pdf", "extra.pdf"}[index])
		if err != nil {
			t.Fatal(err)
		}
		if _, err := part.Write([]byte("%PDF-1.7\ninput")); err != nil {
			t.Fatal(err)
		}
	}
	if err := form.Close(); err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(http.MethodPost, "/api/v1/insert", &body)
	request.Header.Set("Content-Type", form.FormDataContentType())
	return request
}

func TestInsertRouteStreamsOutputAndCleansTemporaryFiles(t *testing.T) {
	processor := &routeProcessor{pageCount: 3}
	router := testRouter(NewPDFHandler(services.NewPDFService(processor)))
	response := httptest.NewRecorder()
	router.ServeHTTP(response, insertRequest(t, 2, map[string]string{"pages": "2", "after": "1"}))

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=inserted.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if !reflect.DeepEqual(processor.collected, []int{1, 5, 2, 3}) {
		t.Fatalf("collected = %v, want [1 5 2 3]", processor.collected)
	}
	if _, err := os.Stat(processor.inputPath); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("temporary input still exists after response: %v", err)
	}
}

func TestInsertRouteRejectsInvalidRequests(t *testing.T) {
	tests := []struct {
		name   string
		files  int
		fields map[string]string
		status int
	}{
		{name: "single PDF", files: 1, fields: map[string]string{"after": "0"}, status: http.StatusBadRequest},
		{name: "three PDFs", files: 3, fields: map[string]string{"after": "0"}, status: http.StatusBadRequest},
		{name: "missing position", files: 2, fields: map[string]string{}, status: http.StatusBadRequest},
		{name: "non numeric position", files: 2, fields: map[string]string{"after": "end"}, status: http.StatusBadRequest},
		{name: "position outside target", files: 2, fields: map[string]string{"after": "4"}, status: http.StatusBadRequest},
		{name: "invalid source pages", files: 2, fields: map[string]string{"after": "0", "pages": "9"}, status: http.StatusBadRequest},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			processor := &routeProcessor{pageCount: 3}
			router := testRouter(NewPDFHandler(services.NewPDFService(processor)))
			response := httptest.NewRecorder()
			router.ServeHTTP(response, insertRequest(t, test.files, test.fields))
			if response.Code != test.status {
				t.Fatalf("status = %d, want %d; body = %s", response.Code, test.status, response.Body.String())
			}
			if processor.collected != nil {
				t.Fatalf("pages were inserted despite an invalid request")
			}
		})
	}
}
