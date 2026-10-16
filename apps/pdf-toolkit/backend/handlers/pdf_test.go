package handlers

import (
	"errors"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSanitizeFilename(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{name: "path traversal", input: `..\..\private.pdf`, expected: "private.pdf"},
		{name: "unsafe characters", input: "rapport final?.pdf", expected: "rapport_final_.pdf"},
		{name: "empty name", input: "...", expected: "document.pdf"},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if actual := sanitizeFilename(test.input); actual != test.expected {
				t.Fatalf("sanitizeFilename(%q) = %q, want %q", test.input, actual, test.expected)
			}
		})
	}
}

func TestSaveUploadEnforcesMaximumSize(t *testing.T) {
	destination := filepath.Join(t.TempDir(), "oversized.pdf")
	err := saveUpload(strings.NewReader("12345"), destination, 4)
	var uploadErr *requestError
	if !errors.As(err, &uploadErr) {
		t.Fatalf("saveUpload error = %v, want requestError", err)
	}
	if uploadErr.status != http.StatusRequestEntityTooLarge {
		t.Fatalf("status = %d, want %d", uploadErr.status, http.StatusRequestEntityTooLarge)
	}
	if _, err := os.Stat(destination); err != nil {
		t.Fatalf("temporary upload should exist for workspace cleanup: %v", err)
	}
}

func TestValidatePDFChecksSignatureAndMIME(t *testing.T) {
	tests := []struct {
		name    string
		content string
		wantErr bool
	}{
		{name: "PDF", content: "%PDF-1.7\n%test", wantErr: false},
		{name: "HTML", content: "<html>not a PDF</html>", wantErr: true},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			filePath := filepath.Join(t.TempDir(), "input")
			if err := os.WriteFile(filePath, []byte(test.content), 0o600); err != nil {
				t.Fatal(err)
			}
			err := validatePDF(filePath)
			if errors.Is(err, errNotPDF) != test.wantErr {
				t.Fatalf("validatePDF error = %v, want not-PDF=%t", err, test.wantErr)
			}
		})
	}
}
