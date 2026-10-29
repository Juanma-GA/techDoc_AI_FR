package web

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestRegisterRoutesServesGeneratedDemoFile(t *testing.T) {
	root := t.TempDir()
	demoDirectory := filepath.Join(root, "generated", "demo")
	if err := os.MkdirAll(demoDirectory, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "generated", "index.html"), []byte("index"), 0o600); err != nil {
		t.Fatal(err)
	}
	const demoContent = "synthetic PDF fixture"
	if err := os.WriteFile(filepath.Join(demoDirectory, "sample.pdf"), []byte(demoContent), 0o600); err != nil {
		t.Fatal(err)
	}

	router := gin.New()
	if err := RegisterRoutes(router, os.DirFS(root)); err != nil {
		t.Fatalf("register routes: %v", err)
	}

	response := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/demo/sample.pdf", nil)
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	if got := response.Body.String(); got != demoContent {
		t.Fatalf("body = %q, want %q", got, demoContent)
	}
}
