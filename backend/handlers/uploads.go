package handlers

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path"
	"path/filepath"
	"strings"
)

const (
	maxFileSize  int64 = 250 * 1024 * 1024
	maxFieldSize int64 = 1024 * 1024
)

var errNotPDF = errors.New("uploaded file is not a PDF")

type requestError struct {
	status  int
	message string
}

func (e *requestError) Error() string {
	return e.message
}

type uploadedPDF struct {
	path string
	name string
}

type multipartUpload struct {
	files  []uploadedPDF
	fields map[string][]string
}

func parseMultipart(request *http.Request, tempDir, fileField string, maxFiles int, textFields ...string) (multipartUpload, error) {
	reader, err := request.MultipartReader()
	if err != nil {
		return multipartUpload{}, &requestError{
			status:  http.StatusBadRequest,
			message: "La requête doit être un formulaire multipart.",
		}
	}

	allowedTextFields := make(map[string]struct{}, len(textFields))
	for _, field := range textFields {
		allowedTextFields[field] = struct{}{}
	}

	result := multipartUpload{fields: make(map[string][]string)}
	for {
		part, err := reader.NextPart()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return multipartUpload{}, &requestError{
				status:  http.StatusBadRequest,
				message: "Le formulaire envoyé est incomplet ou invalide.",
			}
		}

		fieldName := part.FormName()
		if fieldName == "" {
			_ = part.Close()
			return multipartUpload{}, &requestError{
				status:  http.StatusBadRequest,
				message: "Un champ du formulaire est invalide.",
			}
		}

		if part.FileName() == "" {
			if _, allowed := allowedTextFields[fieldName]; !allowed {
				_ = part.Close()
				return multipartUpload{}, &requestError{
					status:  http.StatusBadRequest,
					message: "Le formulaire contient un champ inattendu.",
				}
			}
			value, readErr := io.ReadAll(io.LimitReader(part, maxFieldSize+1))
			closeErr := part.Close()
			if readErr != nil {
				return multipartUpload{}, fmt.Errorf("read form field: %w", readErr)
			}
			if closeErr != nil {
				return multipartUpload{}, fmt.Errorf("close form field: %w", closeErr)
			}
			if int64(len(value)) > maxFieldSize {
				return multipartUpload{}, &requestError{
					status:  http.StatusRequestEntityTooLarge,
					message: "Un champ du formulaire est trop volumineux.",
				}
			}
			result.fields[fieldName] = append(result.fields[fieldName], string(value))
			continue
		}

		if fieldName != fileField {
			_ = part.Close()
			return multipartUpload{}, &requestError{
				status:  http.StatusBadRequest,
				message: "Le formulaire contient un fichier inattendu.",
			}
		}
		if maxFiles > 0 && len(result.files) >= maxFiles {
			_ = part.Close()
			return multipartUpload{}, &requestError{
				status:  http.StatusBadRequest,
				message: "Un seul fichier PDF est accepté pour cette opération.",
			}
		}

		fileName := sanitizeFilename(part.FileName())
		filePath := filepath.Join(tempDir, fmt.Sprintf("input-%04d.pdf", len(result.files)+1))
		if err := saveUpload(part, filePath, maxFileSize); err != nil {
			_ = part.Close()
			var uploadErr *requestError
			if errors.As(err, &uploadErr) {
				return multipartUpload{}, uploadErr
			}
			return multipartUpload{}, fmt.Errorf("save uploaded PDF: %w", err)
		}
		if err := part.Close(); err != nil {
			return multipartUpload{}, fmt.Errorf("close uploaded PDF: %w", err)
		}
		if err := validatePDF(filePath); err != nil {
			if errors.Is(err, errNotPDF) {
				return multipartUpload{}, &requestError{
					status:  http.StatusUnsupportedMediaType,
					message: fmt.Sprintf("« %s » n'est pas un fichier PDF valide.", fileName),
				}
			}
			return multipartUpload{}, fmt.Errorf("inspect uploaded PDF: %w", err)
		}

		result.files = append(result.files, uploadedPDF{path: filePath, name: fileName})
	}

	return result, nil
}

func saveUpload(source io.Reader, destination string, maxSize int64) error {
	file, err := os.OpenFile(destination, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("create temporary PDF: %w", err)
	}

	size, copyErr := io.Copy(file, io.LimitReader(source, maxSize+1))
	closeErr := file.Close()
	if copyErr != nil {
		return fmt.Errorf("copy uploaded PDF: %w", copyErr)
	}
	if closeErr != nil {
		return fmt.Errorf("close temporary PDF: %w", closeErr)
	}
	if size > maxSize {
		return &requestError{
			status:  http.StatusRequestEntityTooLarge,
			message: "Chaque fichier PDF doit faire au maximum 250 Mo.",
		}
	}
	return nil
}

func validatePDF(filePath string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("open temporary PDF: %w", err)
	}
	defer file.Close()

	header := make([]byte, 512)
	size, readErr := io.ReadFull(file, header)
	if readErr != nil && !errors.Is(readErr, io.EOF) && !errors.Is(readErr, io.ErrUnexpectedEOF) {
		return fmt.Errorf("read PDF header: %w", readErr)
	}
	header = header[:size]
	if !bytes.HasPrefix(header, []byte("%PDF-")) || http.DetectContentType(header) != "application/pdf" {
		return errNotPDF
	}
	return nil
}

func sanitizeFilename(fileName string) string {
	fileName = strings.ReplaceAll(fileName, "\\", "/")
	fileName = path.Base(fileName)

	var cleaned strings.Builder
	for _, character := range fileName {
		switch {
		case character >= 'a' && character <= 'z':
			cleaned.WriteRune(character)
		case character >= 'A' && character <= 'Z':
			cleaned.WriteRune(character)
		case character >= '0' && character <= '9':
			cleaned.WriteRune(character)
		case character == '.', character == '-', character == '_':
			cleaned.WriteRune(character)
		default:
			cleaned.WriteByte('_')
		}
	}

	name := strings.Trim(cleaned.String(), ".-_")
	if len(name) > 100 {
		name = name[:100]
	}
	if name == "" {
		return "document.pdf"
	}
	return name
}

func singleField(fields map[string][]string, name string) (string, error) {
	values := fields[name]
	if len(values) != 1 || strings.TrimSpace(values[0]) == "" {
		return "", &requestError{
			status:  http.StatusBadRequest,
			message: "Le champ « " + name + " » est requis.",
		}
	}
	return strings.TrimSpace(values[0]), nil
}
