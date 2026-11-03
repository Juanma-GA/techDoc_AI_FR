package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
	"testing"

	"pdf-toolkit/services"
)

type cropRouteProcessor struct {
	routeProcessor
	crops []services.PDFCropRect
}

func (p *routeProcessor) Crop(_ context.Context, input, output string, _ []services.PDFCropRect) error {
	p.inputPath = input
	return writeRoutePDF(output)
}

func (p *cropRouteProcessor) Crop(_ context.Context, input, output string, crops []services.PDFCropRect) error {
	p.inputPath = input
	p.crops = append([]services.PDFCropRect(nil), crops...)
	return writeRoutePDF(output)
}

func TestCropRouteStreamsPDFAndPassesPageRectangles(t *testing.T) {
	processor := &cropRouteProcessor{routeProcessor: routeProcessor{pageCount: 2}}
	crops := []services.PDFCropRect{
		{Page: 1, X1: 10, Y1: 20, X2: 500, Y2: 700},
		{Page: 2, X1: 15, Y1: 25, X2: 510, Y2: 710},
	}
	rawCrops, err := json.Marshal(crops)
	if err != nil {
		t.Fatal(err)
	}
	request := multipartRequest(t, "/api/v1/crop", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"crops": string(rawCrops),
	})
	response := httptest.NewRecorder()
	testRouter(NewPDFHandler(services.NewPDFService(processor))).ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Disposition"); got != "attachment; filename=cropped.pdf" {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if response.Body.String() != "%PDF-1.7\nprocessed" {
		t.Fatalf("response body = %q", response.Body.String())
	}
	if !reflect.DeepEqual(processor.crops, crops) {
		t.Fatalf("Crop() rectangles = %+v, want %+v", processor.crops, crops)
	}
	if _, err := os.Stat(processor.inputPath); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("temporary PDF still exists after response: %v", err)
	}
}

func TestCropRouteRejectsMalformedRectangles(t *testing.T) {
	request := multipartRequest(t, "/api/v1/crop", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"crops": "{",
	})
	response := httptest.NewRecorder()
	testRouter(NewPDFHandler(services.NewPDFService(&routeProcessor{pageCount: 1}))).ServeHTTP(response, request)

	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusBadRequest)
	}
}
