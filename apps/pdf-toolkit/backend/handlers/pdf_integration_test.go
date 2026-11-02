package handlers

import (
	"bytes"
	"context"
	"errors"
	"image"
	"image/png"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"github.com/gin-gonic/gin"

	"pdf-toolkit/services"
)

type routeProcessor struct {
	pageCount int
	inputPath string
	collected []int
	rotated   []int
	rotation  int
	protected services.PDFProtectionOptions
}

func TestImagesToPDFRouteAcceptsPNGAndStreamsPDF(t *testing.T) {
	handler := NewPDFHandler(services.NewPDFService(&routeProcessor{}))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/images-to-pdf", "images", "pixel.png", testPNGContent(t), nil)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=images.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if response.Body.String() != "%PDF-1.7\nprocessed" {
		t.Fatalf("response body = %q", response.Body.String())
	}
}

func (p *routeProcessor) Merge(_ context.Context, _ []string, output string) error {
	return writeRoutePDF(output)
}

func (p *routeProcessor) ImagesToPDF(_ context.Context, _ []string, output string) error {
	return writeRoutePDF(output)
}

func (p *routeProcessor) Compress(_ context.Context, input, output string) error {
	p.inputPath = input
	return writeRoutePDF(output)
}

func (p *routeProcessor) Clean(_ context.Context, input, output string) error {
	p.inputPath = input
	return writeRoutePDF(output)
}

func (p *routeProcessor) Protect(
	_ context.Context,
	_ string,
	output string,
	options services.PDFProtectionOptions,
) error {
	p.protected = options
	return writeRoutePDF(output)
}

func (p *routeProcessor) ChangeUserPassword(
	_ context.Context,
	_ string,
	output string,
	_ services.PDFPasswordChangeOptions,
) error {
	return writeRoutePDF(output)
}

func (p *routeProcessor) PageCount(_ context.Context, input string) (int, error) {
	p.inputPath = input
	return p.pageCount, nil
}

func (p *routeProcessor) Extract(_ context.Context, input, output string, _ []int) error {
	p.inputPath = input
	return writeRoutePDF(output)
}

func (p *routeProcessor) Delete(_ context.Context, input, output string, _ []int) error {
	p.inputPath = input
	return writeRoutePDF(output)
}

func (p *routeProcessor) Reorder(_ context.Context, input, output string, _ []int) error {
	p.inputPath = input
	return writeRoutePDF(output)
}

func (p *routeProcessor) Collect(_ context.Context, input, output string, pages []int) error {
	p.inputPath = input
	p.collected = append([]int(nil), pages...)
	return writeRoutePDF(output)
}

func (p *routeProcessor) Rotate(_ context.Context, input, output string, pages []int, rotation int) error {
	p.inputPath = input
	p.rotated = append([]int(nil), pages...)
	p.rotation = rotation
	return writeRoutePDF(output)
}

func writeRoutePDF(filePath string) error {
	return os.WriteFile(filePath, []byte("%PDF-1.7\nprocessed"), 0o600)
}

func testPNGContent(t *testing.T) string {
	t.Helper()
	var content bytes.Buffer
	if err := png.Encode(&content, image.NewRGBA(image.Rect(0, 0, 1, 1))); err != nil {
		t.Fatal(err)
	}
	return content.String()
}

func TestExtractRouteStreamsOutputAndCleansTemporaryFiles(t *testing.T) {
	processor := &routeProcessor{pageCount: 3}
	handler := NewPDFHandler(services.NewPDFService(processor))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/extract", "file", `..\..\private.pdf`, "%PDF-1.7\ninput", map[string]string{
		"pages": "1,3",
	})
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Type"); got != "application/pdf" {
		t.Fatalf("Content-Type = %q, want application/pdf", got)
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=extract.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if response.Body.String() != "%PDF-1.7\nprocessed" {
		t.Fatalf("response body = %q", response.Body.String())
	}
	if _, err := os.Stat(processor.inputPath); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("temporary input still exists after response: %v", err)
	}
}

func TestUploadRejectsNonPDFContent(t *testing.T) {
	handler := NewPDFHandler(services.NewPDFService(&routeProcessor{pageCount: 3}))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/extract", "file", "not-a-pdf.pdf", "<html>not a PDF</html>", map[string]string{
		"pages": "1",
	})
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusUnsupportedMediaType {
		t.Fatalf("status = %d, want %d; body = %s", response.Code, http.StatusUnsupportedMediaType, response.Body.String())
	}
}

func TestCompressRouteStreamsOutputAndCleansTemporaryFiles(t *testing.T) {
	processor := &routeProcessor{}
	handler := NewPDFHandler(services.NewPDFService(processor))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/compress", "file", "source.pdf", "%PDF-1.7\ninput", nil)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=compressed.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if response.Body.String() != "%PDF-1.7\nprocessed" {
		t.Fatalf("response body = %q", response.Body.String())
	}
	if _, err := os.Stat(processor.inputPath); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("temporary input still exists after response: %v", err)
	}
}

func TestCleanRouteStreamsOutputAndCleansTemporaryFiles(t *testing.T) {
	processor := &routeProcessor{}
	handler := NewPDFHandler(services.NewPDFService(processor))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/clean", "file", "source.pdf", "%PDF-1.7\ninput", nil)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=cleaned.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if response.Body.String() != "%PDF-1.7\nprocessed" {
		t.Fatalf("response body = %q", response.Body.String())
	}
	if _, err := os.Stat(processor.inputPath); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("temporary input still exists after response: %v", err)
	}
}

func TestReorderRejectsAnIncompletePagePermutation(t *testing.T) {
	handler := NewPDFHandler(services.NewPDFService(&routeProcessor{pageCount: 3}))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/reorder", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"order": "[1,1,3]",
	})
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d; body = %s", response.Code, http.StatusBadRequest, response.Body.String())
	}
}

func TestRotateRouteDefaultsToAllPages(t *testing.T) {
	processor := &routeProcessor{pageCount: 3}
	handler := NewPDFHandler(services.NewPDFService(processor))
	router := testRouter(handler)
	request := multipartRequest(t, "/api/v1/rotate", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"pages":    "",
		"rotation": "90",
	})
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=rotated.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if processor.rotation != 90 {
		t.Fatalf("rotation = %d, want 90", processor.rotation)
	}
	if len(processor.rotated) != 0 {
		t.Fatalf("selected pages = %v, want all pages", processor.rotated)
	}
}

func testRouter(handler *PDFHandler) *gin.Engine {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	handler.RegisterRoutes(router.Group("/api/v1"))
	return router
}

func multipartRequest(
	t *testing.T,
	route, fileField, fileName, fileContent string,
	fields map[string]string,
) *http.Request {
	t.Helper()
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	for name, value := range fields {
		if err := form.WriteField(name, value); err != nil {
			t.Fatal(err)
		}
	}
	file, err := form.CreateFormFile(fileField, fileName)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := file.Write([]byte(fileContent)); err != nil {
		t.Fatal(err)
	}
	if err := form.Close(); err != nil {
		t.Fatal(err)
	}

	request := httptest.NewRequest(http.MethodPost, route, &body)
	request.Header.Set("Content-Type", form.FormDataContentType())
	return request
}
