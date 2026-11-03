package pdf

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"

	"pdf-toolkit/services"
)

func (p *PDFCPU) Protect(
	ctx context.Context,
	input, output string,
	options services.PDFProtectionOptions,
) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	conf := model.NewAESConfiguration(options.UserPassword, options.OwnerPassword, 256)
	conf.Permissions = model.PermissionsNone
	if options.AllowPrint {
		conf.Permissions |= model.PermissionPrintRev2 | model.PermissionPrintRev3
	}
	if options.AllowCopy {
		conf.Permissions |= model.PermissionExtract | model.PermissionExtractRev3
	}
	if options.AllowModify {
		conf.Permissions |= model.PermissionModify
	}
	if options.AllowComments {
		conf.Permissions |= model.PermissionModAnnFillForm
	}
	if options.AllowFormFill || options.AllowSign {
		conf.Permissions |= model.PermissionFillRev3
	}

	if err := api.EncryptFile(input, output, conf); err != nil {
		return fmt.Errorf("pdfcpu encrypt: %w", err)
	}
	return ctx.Err()
}

func (p *PDFCPU) ChangeUserPassword(
	ctx context.Context,
	input, output string,
	options services.PDFPasswordChangeOptions,
) (resultErr error) {
	if err := ctx.Err(); err != nil {
		return err
	}

	conf := model.NewDefaultConfiguration()
	conf.OwnerPW = options.OwnerPassword
	permissions, err := api.GetPermissionsFile(input, conf)
	if err != nil {
		return fmt.Errorf("pdfcpu read permissions: %w", err)
	}
	if permissions == nil {
		return fmt.Errorf("pdfcpu change open password: input PDF is not encrypted")
	}

	tempDir, err := os.MkdirTemp(filepath.Dir(output), ".pdf-toolkit-password-change-")
	if err != nil {
		return fmt.Errorf("create temporary password-change workspace: %w", err)
	}
	defer func() {
		if err := os.RemoveAll(tempDir); err != nil {
			log.Printf("pdf-toolkit: remove decrypted temporary PDF: %v", err)
			resultErr = errors.Join(resultErr, fmt.Errorf("remove decrypted temporary PDF: %w", err))
		}
	}()

	// pdfcpu's direct password-change API requires the old user password. Re-encrypt
	// with the owner password instead, retaining the existing permissions.
	if err := api.DecryptFile(input, filepath.Join(tempDir, "decrypted.pdf"), conf); err != nil {
		return fmt.Errorf("pdfcpu decrypt PDF for password change: %w", err)
	}
	if err := ctx.Err(); err != nil {
		return err
	}

	encryptConf := model.NewAESConfiguration(
		options.NewUserPassword,
		options.OwnerPassword,
		256,
	)
	encryptConf.Permissions = model.PermissionFlags(*permissions)
	if err := api.EncryptFile(filepath.Join(tempDir, "decrypted.pdf"), output, encryptConf); err != nil {
		return fmt.Errorf("pdfcpu re-encrypt PDF with new open password: %w", err)
	}
	return ctx.Err()
}
