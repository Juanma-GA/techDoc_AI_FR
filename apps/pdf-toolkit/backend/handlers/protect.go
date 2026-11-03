package handlers

import (
	"net/http"
	"path/filepath"
	"strconv"

	"github.com/gin-gonic/gin"

	"pdf-toolkit/services"
)

func (h *PDFHandler) Protect(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseMultipart(
		c.Request,
		tempDir,
		"file",
		1,
		"user_password",
		"owner_password",
		"allow_print",
		"allow_copy",
		"allow_modify",
		"allow_comments",
		"allow_form_fill",
		"allow_sign",
	)
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) != 1 {
		writeError(c, http.StatusBadRequest, "Sélectionnez un fichier PDF.")
		return
	}

	userPassword, userErr := singleField(upload.fields, "user_password")
	ownerPassword, ownerErr := singleField(upload.fields, "owner_password")
	allowPrint, printErr := parseProtectionPermission(upload.fields, "allow_print")
	allowCopy, copyErr := parseProtectionPermission(upload.fields, "allow_copy")
	allowModify, modifyErr := parseProtectionPermission(upload.fields, "allow_modify")
	allowComments, commentsErr := parseProtectionPermission(upload.fields, "allow_comments")
	allowFormFill, formFillErr := parseProtectionPermission(upload.fields, "allow_form_fill")
	allowSign, signErr := parseProtectionPermission(upload.fields, "allow_sign")
	if userErr != nil ||
		ownerErr != nil ||
		printErr != nil ||
		copyErr != nil ||
		modifyErr != nil ||
		commentsErr != nil ||
		formFillErr != nil ||
		signErr != nil {
		writeError(c, http.StatusBadRequest, "Vérifiez les options et le PDF sélectionnés.")
		return
	}

	options := services.PDFProtectionOptions{
		UserPassword:  userPassword,
		OwnerPassword: ownerPassword,
		AllowPrint:    allowPrint,
		AllowCopy:     allowCopy,
		AllowModify:   allowModify,
		AllowComments: allowComments,
		AllowFormFill: allowFormFill,
		AllowSign:     allowSign,
	}
	output := filepath.Join(tempDir, "protected.pdf")
	if err := h.service.Protect(c.Request.Context(), upload.files[0].path, output, options); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "protected.pdf")
}

func (h *PDFHandler) ChangePassword(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseMultipart(c.Request, tempDir, "file", 1, "owner_password", "new_user_password")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) != 1 {
		writeError(c, http.StatusBadRequest, "Sélectionnez un fichier PDF.")
		return
	}

	ownerPassword, ownerErr := singleField(upload.fields, "owner_password")
	newUserPassword, newPasswordErr := singleField(upload.fields, "new_user_password")
	if ownerErr != nil || newPasswordErr != nil {
		writeError(c, http.StatusBadRequest, "Vérifiez les options et le PDF sélectionnés.")
		return
	}

	output := filepath.Join(tempDir, "password-updated.pdf")
	if err := h.service.ChangeUserPassword(
		c.Request.Context(),
		upload.files[0].path,
		output,
		services.PDFPasswordChangeOptions{
			OwnerPassword:   ownerPassword,
			NewUserPassword: newUserPassword,
		},
	); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "password-updated.pdf")
}

func parseProtectionPermission(fields map[string][]string, key string) (bool, error) {
	value, err := singleField(fields, key)
	if err != nil {
		return false, err
	}
	allowed, err := strconv.ParseBool(value)
	if err != nil {
		return false, err
	}
	return allowed, nil
}
