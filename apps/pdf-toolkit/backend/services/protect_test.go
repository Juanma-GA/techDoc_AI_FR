package services

import (
	"context"
	"errors"
	"testing"
)

func TestProtectRejectsInvalidPasswords(t *testing.T) {
	tests := []struct {
		name    string
		options PDFProtectionOptions
	}{
		{
			name: "short user password",
			options: PDFProtectionOptions{
				UserPassword:  "short",
				OwnerPassword: "different-owner",
			},
		},
		{
			name: "short owner password",
			options: PDFProtectionOptions{
				UserPassword:  "user-password",
				OwnerPassword: "short",
			},
		},
		{
			name: "passwords match",
			options: PDFProtectionOptions{
				UserPassword:  "same-password",
				OwnerPassword: "same-password",
			},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			err := NewPDFService(&fakeProcessor{}).Protect(
				context.Background(),
				"input.pdf",
				"output.pdf",
				test.options,
			)
			if !errors.Is(err, ErrInvalidInput) {
				t.Fatalf("Protect() error = %v, want ErrInvalidInput", err)
			}
		})
	}
}

func TestChangeUserPasswordRejectsInvalidOptions(t *testing.T) {
	tests := []struct {
		name    string
		options PDFPasswordChangeOptions
	}{
		{
			name: "missing owner password",
			options: PDFPasswordChangeOptions{
				NewUserPassword: "new-open-password",
			},
		},
		{
			name: "short new password",
			options: PDFPasswordChangeOptions{
				OwnerPassword:   "owner-password",
				NewUserPassword: "short",
			},
		},
		{
			name: "new password matches owner password",
			options: PDFPasswordChangeOptions{
				OwnerPassword:   "same-password",
				NewUserPassword: "same-password",
			},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			err := NewPDFService(&fakeProcessor{}).ChangeUserPassword(
				context.Background(),
				"input.pdf",
				"output.pdf",
				test.options,
			)
			if !errors.Is(err, ErrInvalidInput) {
				t.Fatalf("ChangeUserPassword() error = %v, want ErrInvalidInput", err)
			}
		})
	}
}
