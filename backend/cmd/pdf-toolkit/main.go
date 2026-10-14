package main

import (
	"context"
	"errors"
	"log"
	"net"
	"net/http"
	"os"
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

	server := &http.Server{
		Addr:              addr,
		Handler:           router,
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    1 << 20,
	}
	serverErrors := make(chan error, 1)
	go func() {
		serverErrors <- server.Serve(listener)
	}()
	log.Printf("PDF Toolkit listening on http://%s", addr)

	stop, stopSignals := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stopSignals()

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
