package handlers

import (
	"errors"
	"fmt"
	"io"
	"net/http"
	"path/filepath"
	"strings"
)

const maxSignatureImageSize int64 = 10 * 1024 * 1024

type signatureUpload struct {
	pdfPath       string
	signaturePath string
	fields        map[string][]string
}

func parseSignatureMultipart(request *http.Request, tempDir string) (signatureUpload, error) {
	reader, err := request.MultipartReader()
	if err != nil {
		return signatureUpload{}, &requestError{
			status:  http.StatusBadRequest,
			message: "La requête doit être un formulaire multipart.",
		}
	}

	result := signatureUpload{fields: make(map[string][]string)}
	seenFiles := make(map[string]bool)
	allowedFields := map[string]struct{}{
		"page": {}, "x": {}, "y": {}, "width": {},
	}
	for {
		part, err := reader.NextPart()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return signatureUpload{}, &requestError{
				status:  http.StatusBadRequest,
				message: "Le formulaire envoyé est incomplet ou invalide.",
			}
		}

		fieldName := part.FormName()
		if fieldName == "" {
			_ = part.Close()
			return signatureUpload{}, &requestError{
				status:  http.StatusBadRequest,
				message: "Un champ du formulaire est invalide.",
			}
		}

		if part.FileName() == "" {
			if _, allowed := allowedFields[fieldName]; !allowed {
				_ = part.Close()
				return signatureUpload{}, &requestError{
					status:  http.StatusBadRequest,
					message: "Le formulaire contient un champ inattendu.",
				}
			}
			value, readErr := io.ReadAll(io.LimitReader(part, maxFieldSize+1))
			closeErr := part.Close()
			if readErr != nil {
				return signatureUpload{}, fmt.Errorf("read signature form field: %w", readErr)
			}
			if closeErr != nil {
				return signatureUpload{}, fmt.Errorf("close signature form field: %w", closeErr)
			}
			if int64(len(value)) > maxFieldSize {
				return signatureUpload{}, &requestError{
					status:  http.StatusRequestEntityTooLarge,
					message: "Un champ du formulaire est trop volumineux.",
				}
			}
			result.fields[fieldName] = append(result.fields[fieldName], string(value))
			continue
		}

		if fieldName != "file" && fieldName != "signature" {
			_ = part.Close()
			return signatureUpload{}, &requestError{
				status:  http.StatusBadRequest,
				message: "Le formulaire contient un fichier inattendu.",
			}
		}
		if seenFiles[fieldName] {
			_ = part.Close()
			return signatureUpload{}, &requestError{
				status:  http.StatusBadRequest,
				message: "Le formulaire contient un fichier inattendu.",
			}
		}
		seenFiles[fieldName] = true

		fileName := sanitizeFilename(part.FileName())
		extension := ".pdf"
		maxSize := maxFileSize
		if fieldName == "signature" {
			extension = strings.ToLower(filepath.Ext(fileName))
			if extension != ".png" && extension != ".jpg" && extension != ".jpeg" {
				_ = part.Close()
				return signatureUpload{}, &requestError{
					status:  http.StatusUnsupportedMediaType,
					message: fmt.Sprintf("« %s » n'est pas une image PNG ou JPEG valide.", fileName),
				}
			}
			maxSize = maxSignatureImageSize
		}

		filePath := filepath.Join(tempDir, fieldName+extension)
		if err := saveUpload(part, filePath, maxSize); err != nil {
			_ = part.Close()
			var uploadErr *requestError
			if fieldName == "signature" && errors.As(err, &uploadErr) &&
				uploadErr.status == http.StatusRequestEntityTooLarge {
				return signatureUpload{}, &requestError{
					status:  http.StatusRequestEntityTooLarge,
					message: "L'image de signature dépasse la limite de 10 Mo.",
				}
			}
			if errors.As(err, &uploadErr) {
				return signatureUpload{}, uploadErr
			}
			return signatureUpload{}, fmt.Errorf("save signature upload: %w", err)
		}
		if err := part.Close(); err != nil {
			return signatureUpload{}, fmt.Errorf("close signature upload: %w", err)
		}

		var validationErr error
		if fieldName == "signature" {
			validationErr = validateImage(filePath, extension)
		} else {
			validationErr = validatePDF(filePath)
		}
		if validationErr != nil {
			if errors.Is(validationErr, errNotPDF) {
				return signatureUpload{}, &requestError{
					status:  http.StatusUnsupportedMediaType,
					message: fmt.Sprintf("« %s » n'est pas un fichier PDF valide.", fileName),
				}
			}
			if errors.Is(validationErr, errNotImage) {
				return signatureUpload{}, &requestError{
					status:  http.StatusUnsupportedMediaType,
					message: fmt.Sprintf("« %s » n'est pas une image PNG ou JPEG valide.", fileName),
				}
			}
			return signatureUpload{}, fmt.Errorf("validate signature upload: %w", validationErr)
		}

		if fieldName == "signature" {
			result.signaturePath = filePath
		} else {
			result.pdfPath = filePath
		}
	}

	if result.pdfPath == "" {
		return signatureUpload{}, &requestError{
			status:  http.StatusBadRequest,
			message: "Sélectionnez un fichier PDF.",
		}
	}
	if result.signaturePath == "" {
		return signatureUpload{}, &requestError{
			status:  http.StatusBadRequest,
			message: "Sélectionnez au moins une image PNG ou JPEG.",
		}
	}
	return result, nil
}
