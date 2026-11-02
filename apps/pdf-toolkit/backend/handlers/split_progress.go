package handlers

import (
	"net/http"
	"sync"

	"github.com/gin-gonic/gin"
)

type splitProgressState struct {
	Phase     string `json:"phase"`
	Completed int    `json:"completed"`
	Total     int    `json:"total"`
}

type splitProgressStore struct {
	mu   sync.RWMutex
	jobs map[string]splitProgressState
}

func newSplitProgressStore() *splitProgressStore {
	return &splitProgressStore{jobs: make(map[string]splitProgressState)}
}

func (s *splitProgressStore) start(id string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.jobs[id]; exists {
		return false
	}
	s.jobs[id] = splitProgressState{Phase: "processing"}
	return true
}

func (s *splitProgressStore) update(id, phase string, completed, total int) {
	if id == "" {
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.jobs[id]; !exists {
		return
	}
	s.jobs[id] = splitProgressState{Phase: phase, Completed: completed, Total: total}
}

func (s *splitProgressStore) get(id string) (splitProgressState, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	progress, exists := s.jobs[id]
	return progress, exists
}

func (s *splitProgressStore) remove(id string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.jobs, id)
}

func isSplitProgressID(id string) bool {
	if len(id) != 36 {
		return false
	}
	for index, character := range id {
		switch index {
		case 8, 13, 18, 23:
			if character != '-' {
				return false
			}
		default:
			if !((character >= '0' && character <= '9') ||
				(character >= 'a' && character <= 'f') ||
				(character >= 'A' && character <= 'F')) {
				return false
			}
		}
	}
	return true
}

func (h *PDFHandler) SplitProgress(c *gin.Context) {
	jobID := c.Param("jobID")
	if !isSplitProgressID(jobID) {
		writeError(c, http.StatusBadRequest, "L’identifiant de progression est invalide.")
		return
	}
	progress, exists := h.splitProgress.get(jobID)
	if !exists {
		writeError(c, http.StatusNotFound, "Progression introuvable.")
		return
	}
	c.Header("Cache-Control", "no-store")
	c.JSON(http.StatusOK, progress)
}
