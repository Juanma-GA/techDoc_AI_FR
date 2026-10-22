package handlers

import (
	"bytes"
	"context"
	"errors"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"pdf-toolkit/services"
)

func (p *routeProcessor) StampSignature(
	_ context.Context,
	input, _, output string,
	_ services.SignatureStampOptions,
) error {
	p.inputPath = input
	return writeRoutePDF(output)
}

func TestSignatureRouteStreamsNewPDFAndCleansTemporaryFiles(t *testing.T) {
	processor := &routeProcessor{pageCount: 3}
	handler := NewPDFHandler(services.NewPDFService(processor))
	router := testRouter(handler)

	request := signatureMultipartRequest(t, map[string]string{
		"page":           "2",
		"x":              "0.2",
		"y":              "0.6",
		"width":          "0.3",
		"name_text":      "Ada Lovelace",
		"name_x":         "0.1",
		"name_y":         "0.86",
		"name_font_size": "14",
		"date_text":      "22/10/2026",
		"date_x":         "0.1",
		"date_y":         "0.92",
		"date_font_size": "14",
	})
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=signed.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if response.Body.String() != "%PDF-1.7\nprocessed" {
		t.Fatalf("response body = %q", response.Body.String())
	}
	if _, err := os.Stat(processor.inputPath); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("temporary PDF still exists after response: %v", err)
	}
}

func TestSignatureRouteRejectsTextWithoutPlacement(t *testing.T) {
	handler := NewPDFHandler(services.NewPDFService(&routeProcessor{pageCount: 3}))
	router := testRouter(handler)
	request := signatureMultipartRequest(t, map[string]string{
		"page":      "1",
		"x":         "0.2",
		"y":         "0.6",
		"width":     "0.3",
		"name_text": "Ada Lovelace",
	})
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusBadRequest)
	}
}

func TestSignatureRouteRejectsInvalidPageValue(t *testing.T) {
	processor := &routeProcessor{pageCount: 3}
	handler := NewPDFHandler(services.NewPDFService(processor))
	router := testRouter(handler)

	request := signatureMultipartRequest(t, map[string]string{
		"page":  "NaN",
		"x":     "0.2",
		"y":     "0.6",
		"width": "0.3",
	})
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusBadRequest)
	}
}

func TestParseSignatureMultipartRejectsImagesAboveTenMegabytes(t *testing.T) {
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	pdfPart, err := form.CreateFormFile("file", "input.pdf")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pdfPart.Write([]byte("%PDF-1.7\ninput")); err != nil {
		t.Fatal(err)
	}
	signaturePart, err := form.CreateFormFile("signature", "signature.png")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := signaturePart.Write(bytes.Repeat([]byte("x"), int(maxSignatureImageSize+1))); err != nil {
		t.Fatal(err)
	}
	if err := form.Close(); err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(http.MethodPost, "/api/v1/signature", &body)
	request.Header.Set("Content-Type", form.FormDataContentType())

	_, err = parseSignatureMultipart(request, t.TempDir())
	var requestErr *requestError
	if !errors.As(err, &requestErr) || requestErr.status != http.StatusRequestEntityTooLarge {
		t.Fatalf("parseSignatureMultipart() error = %v, want HTTP 413", err)
	}
}

func signatureMultipartRequest(t *testing.T, fields map[string]string) *http.Request {
	t.Helper()
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	for name, value := range fields {
		if err := form.WriteField(name, value); err != nil {
			t.Fatal(err)
		}
	}
	pdfPart, err := form.CreateFormFile("file", "input.pdf")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pdfPart.Write([]byte("%PDF-1.7\ninput")); err != nil {
		t.Fatal(err)
	}
	signaturePart, err := form.CreateFormFile("signature", "signature.png")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := signaturePart.Write([]byte(testPNGContent(t))); err != nil {
		t.Fatal(err)
	}
	if err := form.Close(); err != nil {
		t.Fatal(err)
	}

	request := httptest.NewRequest(http.MethodPost, "/api/v1/signature", &body)
	request.Header.Set("Content-Type", form.FormDataContentType())
	return request
}
