package pdf

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"

	"pdf-toolkit/services"
)

func TestPDFCPUProtectEncryptsWithUserPasswordAndPermissions(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "source.pdf")
	output := filepath.Join(tempDir, "protected.pdf")
	if err := os.WriteFile(input, testPDF(t, 1), 0o600); err != nil {
		t.Fatal(err)
	}

	options := services.PDFProtectionOptions{
		UserPassword:  "user-password",
		OwnerPassword: "owner-password",
		AllowPrint:    true,
		AllowComments: true,
		AllowFormFill: true,
		AllowSign:     true,
	}
	if err := NewPDFCPU().Protect(context.Background(), input, output, options); err != nil {
		t.Fatalf("Protect() error = %v", err)
	}

	if err := api.ValidateFile(output, model.NewDefaultConfiguration()); err == nil {
		t.Fatal("ValidateFile() without a password succeeded for encrypted output")
	}
	conf := model.NewDefaultConfiguration()
	conf.UserPW = options.UserPassword
	if err := api.ValidateFile(output, conf); err != nil {
		t.Fatalf("ValidateFile() with user password error = %v", err)
	}

	file, err := os.Open(output)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	permissions, err := api.Permissions(file, conf)
	if err != nil {
		t.Fatalf("Permissions() error = %v", err)
	}
	if model.PermissionFlags(permissions)&model.PermissionPrintRev3 == 0 {
		t.Fatal("Permissions() did not include print permission")
	}
	if model.PermissionFlags(permissions)&model.PermissionExtractRev3 != 0 {
		t.Fatal("Permissions() unexpectedly included copy permission")
	}
	if model.PermissionFlags(permissions)&model.PermissionModAnnFillForm == 0 {
		t.Fatal("Permissions() did not include comments and annotations")
	}
	if model.PermissionFlags(permissions)&model.PermissionFillRev3 == 0 {
		t.Fatal("Permissions() did not include form filling and signing")
	}
}

func TestPDFCPUChangesOpenPasswordWithOwnerPassword(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "source.pdf")
	protected := filepath.Join(tempDir, "protected.pdf")
	updated := filepath.Join(tempDir, "password-updated.pdf")
	if err := os.WriteFile(input, testPDF(t, 1), 0o600); err != nil {
		t.Fatal(err)
	}

	processor := NewPDFCPU()
	ownerPassword := "owner-password"
	if err := processor.Protect(context.Background(), input, protected, services.PDFProtectionOptions{
		UserPassword:  "old-open-password",
		OwnerPassword: ownerPassword,
		AllowPrint:    true,
		AllowComments: true,
		AllowFormFill: true,
		AllowSign:     true,
	}); err != nil {
		t.Fatalf("Protect() error = %v", err)
	}
	invalidOutput := filepath.Join(tempDir, "invalid-password-update.pdf")
	if err := processor.ChangeUserPassword(
		context.Background(),
		protected,
		invalidOutput,
		services.PDFPasswordChangeOptions{
			OwnerPassword:   "wrong-owner-password",
			NewUserPassword: "new-open-password",
		},
	); err == nil {
		t.Fatal("ChangeUserPassword() with a wrong owner password succeeded")
	}
	if _, err := os.Stat(invalidOutput); !os.IsNotExist(err) {
		t.Fatalf("password-change output exists after invalid owner password: %v", err)
	}
	if err := processor.ChangeUserPassword(
		context.Background(),
		protected,
		updated,
		services.PDFPasswordChangeOptions{
			OwnerPassword:   ownerPassword,
			NewUserPassword: "new-open-password",
		},
	); err != nil {
		t.Fatalf("ChangeUserPassword() error = %v", err)
	}

	newUserConf := model.NewDefaultConfiguration()
	newUserConf.UserPW = "new-open-password"
	if err := api.ValidateFile(updated, newUserConf); err != nil {
		t.Fatalf("ValidateFile() with new user password error = %v", err)
	}
	permissions, err := api.GetPermissionsFile(updated, newUserConf)
	if err != nil {
		t.Fatalf("GetPermissionsFile() after password change error = %v", err)
	}
	if permissions == nil ||
		model.PermissionFlags(*permissions)&model.PermissionPrintRev3 == 0 ||
		model.PermissionFlags(*permissions)&model.PermissionExtractRev3 != 0 ||
		model.PermissionFlags(*permissions)&model.PermissionModAnnFillForm == 0 ||
		model.PermissionFlags(*permissions)&model.PermissionFillRev3 == 0 {
		t.Fatalf("permissions after password change = %v, want print/comments/form fill allowed and copy denied", permissions)
	}
	oldUserConf := model.NewDefaultConfiguration()
	oldUserConf.UserPW = "old-open-password"
	if err := api.ValidateFile(updated, oldUserConf); err == nil {
		t.Fatal("ValidateFile() with old user password succeeded after password change")
	}
	ownerConf := model.NewDefaultConfiguration()
	ownerConf.OwnerPW = ownerPassword
	if err := api.ValidateFile(updated, ownerConf); err != nil {
		t.Fatalf("ValidateFile() with owner password error = %v", err)
	}
}
