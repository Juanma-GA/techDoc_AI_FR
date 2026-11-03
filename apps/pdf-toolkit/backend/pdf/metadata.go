package pdf

import (
	"context"
	"errors"
	"fmt"
	"os"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/types"

	"pdf-toolkit/services"
)

func (p *PDFCPU) EditMetadata(ctx context.Context, input, output string, metadata services.PDFMetadata) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	file, err := os.Open(input)
	if err != nil {
		return fmt.Errorf("pdfcpu metadata open input: %w", err)
	}
	conf := model.NewDefaultConfiguration()
	conf.Cmd = model.ADDPROPERTIES
	document, readErr := api.ReadValidateAndOptimize(file, conf)
	if err := errors.Join(readErr, file.Close()); err != nil {
		return fmt.Errorf("pdfcpu metadata read input: %w", err)
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	info := types.NewDict()
	if document.Info != nil {
		info, err = document.DereferenceDict(*document.Info)
		if err != nil || info == nil {
			return fmt.Errorf("pdfcpu metadata read document info: %w", errors.Join(err, services.ErrInvalidPDF))
		}
	} else {
		document.Info, err = document.IndRefForNewObject(info)
		if err != nil {
			return fmt.Errorf("pdfcpu metadata create document info: %w", err)
		}
	}
	for key, value := range map[string]string{
		"Title": metadata.Title, "Author": metadata.Author,
		"Subject": metadata.Subject, "Keywords": metadata.Keywords,
	} {
		if value == "" {
			info.Delete(key)
			continue
		}
		encoded, err := types.EscapedUTF16String(value)
		if err != nil {
			return fmt.Errorf("pdfcpu metadata encode %s: %w", key, err)
		}
		info.Update(key, types.StringLiteral(*encoded))
	}
	catalog, err := document.Catalog()
	if err != nil {
		return fmt.Errorf("pdfcpu metadata read catalog: %w", err)
	}
	// XMP may override the edited Info fields in readers; discard stale document XMP.
	catalog.Delete("Metadata")
	document.CatalogXMPMeta = nil
	if err := ctx.Err(); err != nil {
		return err
	}

	file, err = os.OpenFile(output, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("%w: create metadata output: %w", services.ErrOutputWrite, err)
	}
	writeErr := api.WriteContext(document, file)
	if err := errors.Join(writeErr, file.Close(), ctx.Err()); err != nil {
		removeErr := os.Remove(output)
		if errors.Is(removeErr, os.ErrNotExist) {
			removeErr = nil
		}
		return errors.Join(
			fmt.Errorf("%w: write metadata output: %w", services.ErrOutputWrite, err),
			removeErr,
		)
	}
	return nil
}
