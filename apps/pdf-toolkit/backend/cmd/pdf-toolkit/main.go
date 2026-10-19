package main

import (
	"context"
	"errors"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"

	"pdf-toolkit/handlers"
	pdfadapter "pdf-toolkit/pdf"
	"pdf-toolkit/services"
	"pdf-toolkit/web"
)

func main() {
	addr := strings.TrimSpace(os.Getenv("PDF_TOOLKIT_ADDR"))
	if addr == "" {
		addr = "127.0.0.1:8085"
	}

	staticFiles, err := web.Files()
	if err != nil {
		log.Fatalf("load embedded frontend: %v", err)
	}

	gin.SetMode(gin.ReleaseMode)
	router := gin.New()
	router.Use(gin.Logger(), gin.Recovery())
	handlers.NewPDFHandler(services.NewPDFService(pdfadapter.NewPDFCPU())).
		RegisterRoutes(router.Group("/api/v1"))
	if err := web.RegisterRoutes(router, staticFiles); err != nil {
		log.Fatalf("register frontend: %v", err)
	}
	router.NoRoute(func(c *gin.Context) {
		c.JSON(http.StatusNotFound, gin.H{"error": "Route introuvable."})
	})

	listener, err := net.Listen("tcp", addr)
	if err != nil {
		log.Fatalf("listen on %s: %v", addr, err)
	}
	actualAddr := listener.Addr().String()

	server := &http.Server{
		Addr:              actualAddr,
		Handler:           router,
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    1 << 20,
	}
	serverErrors := make(chan error, 1)
	go func() {
		serverErrors <- server.Serve(listener)
	}()
	stop, stopSignals := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stopSignals()

	log.Printf("PDF Toolkit listening on http://%s", actualAddr)
	if readyFile := strings.TrimSpace(os.Getenv("PDF_TOOLKIT_READY_FILE")); readyFile != "" {
		tempFile := readyFile + ".tmp"
		if err := os.WriteFile(tempFile, []byte(actualAddr), 0o600); err != nil {
			log.Fatalf("write backend readiness file: %v", err)
		}
		if err := os.Rename(tempFile, readyFile); err != nil {
			log.Fatalf("write backend readiness file: %v", err)
		}
		defer func() {
			if err := os.Remove(readyFile); err != nil && !errors.Is(err, os.ErrNotExist) {
				log.Printf("remove backend readiness file: %v", err)
			}
			if err := os.Remove(tempFile); err != nil && !errors.Is(err, os.ErrNotExist) {
				log.Printf("remove temporary backend readiness file: %v", err)
			}
		}()
	}
	if os.Getenv("PDF_TOOLKIT_OPEN_BROWSER") == "1" {
		if err := exec.Command("cmd", "/c", "start", "", "http://"+addr+"/").Run(); err != nil {
			log.Printf("open browser: %v", err)
		}
	}

	select {
	case err := <-serverErrors:
		if !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("serve HTTP: %v", err)
		}
		return
	case <-stop.Done():
		shutdown, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdown); err != nil {
			if closeErr := server.Close(); closeErr != nil {
				log.Printf("close HTTP server after shutdown error: %v", closeErr)
			}
			log.Printf("graceful shutdown: %v", err)
		}
		if err := <-serverErrors; err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Printf("HTTP server stopped: %v", err)
		}
	}
}
