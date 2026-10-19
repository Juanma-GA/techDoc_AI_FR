package web

import (
	"embed"
	"errors"
	"fmt"
	"io/fs"
	"mime"
	"net/http"

	"github.com/gin-gonic/gin"
)

//go:embed all:static
var embeddedFiles embed.FS

func Files() (fs.FS, error) {
	return fs.Sub(embeddedFiles, "static")
}

func RegisterRoutes(router *gin.Engine, files fs.FS) error {
	indexPath := "index.html"
	assetPath := "assets"
	if _, err := fs.Stat(files, "generated/index.html"); err == nil {
		indexPath = "generated/index.html"
		assetPath = "generated/assets"
	} else if !errors.Is(err, fs.ErrNotExist) {
		return fmt.Errorf("inspect generated frontend: %w", err)
	}

	index, err := fs.ReadFile(files, indexPath)
	if err != nil {
		return fmt.Errorf("read frontend index: %w", err)
	}
	router.GET("/", func(c *gin.Context) {
		c.Header("Cache-Control", "no-store")
		c.Data(http.StatusOK, "text/html; charset=utf-8", index)
	})

	if err := mime.AddExtensionType(".mjs", "text/javascript"); err != nil {
		return fmt.Errorf("register JavaScript module MIME type: %w", err)
	}
	assets, err := fs.Sub(files, assetPath)
	if err == nil {
		fileServer := http.StripPrefix("/assets/", http.FileServer(http.FS(assets)))
		router.GET("/assets/*filepath", gin.WrapH(fileServer))
	} else if !errors.Is(err, fs.ErrNotExist) {
		return fmt.Errorf("open frontend assets: %w", err)
	}
	return nil
}
