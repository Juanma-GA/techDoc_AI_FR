package handlers

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"pdf-toolkit/services"
)

type directRouteProcessor struct {
	*routeProcessor
	document *directRouteSplitDocument
}

type directRouteSplitDocument struct {
	pageCount            int
	outputs              []string
	visibleDuringProcess bool
}

func (p *directRouteProcessor) OpenSplitDocument(context.Context, string) (services.SplitDocument, error) {
	return p.document, nil
}

func (d *directRouteSplitDocument) PageCount() int {
	return d.pageCount
}

func (d *directRouteSplitDocument) Extract(ctx context.Context, output string, _ []int) error {
	if len(d.outputs) > 0 {
		if _, err := os.Stat(d.outputs[0]); err == nil {
			d.visibleDuringProcess = true
		} else {
			return err
		}
	}
	if err := os.WriteFile(output, []byte("%PDF-1.7\nprocessed"), 0o600); err != nil {
		return err
	}
	d.outputs = append(d.outputs, output)
	return ctx.Err()
}

func (d *directRouteSplitDocument) Close() error {
	return nil
}

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

func TestSplitProgressRouteReturnsCurrentProgress(t *testing.T) {
	handler := NewPDFHandler(services.NewPDFService(&routeProcessor{pageCount: 1}))
	jobID := "4d63df90-6c8c-4c48-b853-671ec1fb2644"
	if !handler.splitProgress.start(jobID) {
		t.Fatal("progress job was not created")
	}
	handler.splitProgress.update(jobID, "extracting", 2, 5)

	response := httptest.NewRecorder()
	testRouter(handler).ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/api/v1/split/progress/"+jobID, nil))
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d; body = %s", response.Code, http.StatusOK, response.Body.String())
	}
	var progress splitProgressState
	if err := json.Unmarshal(response.Body.Bytes(), &progress); err != nil {
		t.Fatal(err)
	}
	if progress != (splitProgressState{Phase: "extracting", Completed: 2, Total: 5}) {
		t.Fatalf("progress = %+v, want extracting 2/5", progress)
	}
	if got := response.Header().Get("Cache-Control"); got != "no-store" {
		t.Fatalf("Cache-Control = %q, want no-store", got)
	}
}

func TestWriteSplitArchiveReportsProgressAfterEachFile(t *testing.T) {
	tempDir := t.TempDir()
	archivePath := filepath.Join(tempDir, "split.zip")
	if err := os.WriteFile(archivePath, []byte("old archive"), 0o600); err != nil {
		t.Fatal(err)
	}
	outputs := make([]services.SplitOutput, 2)
	for index, name := range []string{"part-1.pdf", "part-2.pdf"} {
		path := filepath.Join(tempDir, name)
		if err := os.WriteFile(path, []byte("%PDF-1.7"), 0o600); err != nil {
			t.Fatal(err)
		}
		outputs[index] = services.SplitOutput{Name: filepath.Base(path), Path: path}
	}
	var completed []int
	var totals []int
	err := writeSplitArchive(archivePath, "folder", outputs, func(done, total int) {
		completed = append(completed, done)
		totals = append(totals, total)
	})
	if err != nil {
		t.Fatalf("writeSplitArchive() error = %v", err)
	}
	if len(completed) != 2 || completed[0] != 1 || completed[1] != 2 {
		t.Fatalf("archive progress = %v, want [1 2]", completed)
	}
	if len(totals) != 2 || totals[0] != 2 || totals[1] != 2 {
		t.Fatalf("archive totals = %v, want [2 2]", totals)
	}
}

func TestSplitRouteWritesInChosenDirectoryThenKeepsOnlyZip(t *testing.T) {
	outputDir := t.TempDir()
	existingPDF := filepath.Join(outputDir, "DOC_A_rev1.pdf")
	if err := os.WriteFile(existingPDF, []byte("keep"), 0o600); err != nil {
		t.Fatal(err)
	}
	zipPath := filepath.Join(outputDir, "source split.zip")
	if err := os.WriteFile(zipPath, []byte("old archive"), 0o600); err != nil {
		t.Fatal(err)
	}
	document := &directRouteSplitDocument{pageCount: 4}
	processor := &directRouteProcessor{routeProcessor: &routeProcessor{pageCount: 4}, document: document}
	handler := NewPDFHandler(services.NewPDFService(processor))
	request := multipartRequest(t, "/api/v1/split", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"groups":   `[{"name":"DOC_A_rev1","pages":"1-2"},{"name":"DOC_B_rev1","pages":"3-4"}]`,
		"folder":   "source split",
		"zip_path": zipPath,
	})
	request.Header.Set(directSplitExportHeader, "1")
	request.Header.Set("Origin", "http://127.0.0.1:8085")
	response := httptest.NewRecorder()
	testRouter(handler).ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	var result struct {
		FileName string `json:"file_name"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.FileName != filepath.Base(zipPath) {
		t.Fatalf("file_name = %q, want %q", result.FileName, filepath.Base(zipPath))
	}
	if !document.visibleDuringProcess {
		t.Fatal("first output was not present while the next file was being split")
	}
	if content, err := os.ReadFile(existingPDF); err != nil || string(content) != "keep" {
		t.Fatalf("existing PDF = %q, err = %v; it must not be overwritten", content, err)
	}
	for _, name := range []string{"DOC_A_rev1_2.pdf", "DOC_B_rev1.pdf"} {
		if _, err := os.Stat(filepath.Join(outputDir, name)); !errors.Is(err, os.ErrNotExist) {
			t.Fatalf("intermediate PDF %q remains after success, err = %v", name, err)
		}
	}
	archiveBytes, err := os.ReadFile(zipPath)
	if err != nil {
		t.Fatal(err)
	}
	archive, err := zip.NewReader(bytes.NewReader(archiveBytes), int64(len(archiveBytes)))
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"source split/DOC_A_rev1_2.pdf", "source split/DOC_B_rev1.pdf"}
	if len(archive.File) != len(want) {
		t.Fatalf("archive entries = %d, want %d", len(archive.File), len(want))
	}
	for index, entry := range archive.File {
		if entry.Name != want[index] {
			t.Fatalf("entry %d = %q, want %q", index, entry.Name, want[index])
		}
	}
}

func TestSplitRouteRejectsDirectExportFromNonDesktopRequest(t *testing.T) {
	handler := NewPDFHandler(services.NewPDFService(&routeProcessor{pageCount: 1}))
	request := multipartRequest(t, "/api/v1/split", "file", "source.pdf", "%PDF-1.7\ninput", map[string]string{
		"groups":   `[{"name":"DOC_A","pages":"1"}]`,
		"zip_path": filepath.Join(t.TempDir(), "output.zip"),
	})
	request.Header.Set("Origin", "https://example.com")
	response := httptest.NewRecorder()
	testRouter(handler).ServeHTTP(response, request)
	if response.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want %d; body = %s", response.Code, http.StatusForbidden, response.Body.String())
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
