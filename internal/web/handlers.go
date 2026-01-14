package web

import (
	"html/template"
	"log"
	"net/http"
	"strconv"

	"github.com/gorilla/sessions"

	"smtp-proxy/internal/config"
	"smtp-proxy/internal/database"
)

// Handler contains all HTTP handlers for the web interface
type Handler struct {
	cfg       *config.Config
	emailRepo *database.EmailRepository
	userRepo  *database.UserRepository
	store     *sessions.CookieStore
	auth      *AuthMiddleware
}

// NewHandler creates a new Handler with all dependencies
func NewHandler(cfg *config.Config, emailRepo *database.EmailRepository, userRepo *database.UserRepository, store *sessions.CookieStore) *Handler {
	return &Handler{
		cfg:       cfg,
		emailRepo: emailRepo,
		userRepo:  userRepo,
		store:     store,
		auth:      NewAuthMiddleware(store, cfg.Web.SessionName),
	}
}

// parseTemplate parses a page template together with the base template
func parseTemplate(name string) *template.Template {
	return template.Must(template.ParseFiles("templates/base.html", "templates/"+name))
}

// LoginPage renders the login form
func (h *Handler) LoginPage(w http.ResponseWriter, r *http.Request) {
	// If already logged in, redirect to emails
	if _, ok := h.auth.GetUserID(r); ok {
		http.Redirect(w, r, "/emails", http.StatusSeeOther)
		return
	}

	data := map[string]interface{}{
		"Title": "Login",
		"Error": r.URL.Query().Get("error") != "",
	}
	h.renderTemplate(w, "login.html", data)
}

// LoginSubmit processes the login form submission
func (h *Handler) LoginSubmit(w http.ResponseWriter, r *http.Request) {
	username := r.FormValue("username")
	password := r.FormValue("password")

	user, err := h.userRepo.GetByUsername(username)
	if err != nil {
		log.Printf("Login failed for user %s: user not found", username)
		http.Redirect(w, r, "/login?error=1", http.StatusSeeOther)
		return
	}

	if !h.userRepo.VerifyPassword(user, password) {
		log.Printf("Login failed for user %s: invalid password", username)
		http.Redirect(w, r, "/login?error=1", http.StatusSeeOther)
		return
	}

	// Create session
	session, err := h.store.Get(r, h.cfg.Web.SessionName)
	if err != nil {
		log.Printf("Failed to get session: %v", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	session.Values["user_id"] = user.ID
	session.Values["username"] = user.Username

	log.Printf("DEBUG: Setting session values - user_id: %v (type: %T), username: %v", user.ID, user.ID, user.Username)

	if err := session.Save(r, w); err != nil {
		log.Printf("Failed to save session: %v", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	log.Printf("User %s logged in successfully (session saved)", username)
	http.Redirect(w, r, "/emails", http.StatusSeeOther)
}

// Logout destroys the session and redirects to login
func (h *Handler) Logout(w http.ResponseWriter, r *http.Request) {
	session, err := h.store.Get(r, h.cfg.Web.SessionName)
	if err == nil {
		username, _ := session.Values["username"].(string)
		log.Printf("User %s logged out", username)

		session.Options.MaxAge = -1
		session.Save(r, w)
	}

	http.Redirect(w, r, "/login", http.StatusSeeOther)
}

// EmailList displays all received emails
func (h *Handler) EmailList(w http.ResponseWriter, r *http.Request) {
	emails, err := h.emailRepo.GetAll()
	if err != nil {
		log.Printf("Failed to fetch emails: %v", err)
		http.Error(w, "Failed to fetch emails", http.StatusInternalServerError)
		return
	}

	username, _ := h.auth.GetUsername(r)

	var message string
	if r.URL.Query().Get("message") == "wiped" {
		message = "All emails have been deleted successfully."
	}

	data := map[string]interface{}{
		"Title":    "Emails",
		"Username": username,
		"Emails":   emails,
		"Count":    len(emails),
		"Message":  message,
	}
	h.renderTemplate(w, "emails.html", data)
}

// EmailDetail shows a single email's details
func (h *Handler) EmailDetail(w http.ResponseWriter, r *http.Request) {
	idStr := r.PathValue("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		http.Error(w, "Invalid email ID", http.StatusBadRequest)
		return
	}

	email, err := h.emailRepo.GetByID(id)
	if err != nil {
		log.Printf("Email not found: %v", err)
		http.NotFound(w, r)
		return
	}

	username, _ := h.auth.GetUsername(r)

	data := map[string]interface{}{
		"Title":    "Email Details",
		"Username": username,
		"Email":    email,
	}
	h.renderTemplate(w, "email_detail.html", data)
}

// WipeEmails deletes all emails from the database
func (h *Handler) WipeEmails(w http.ResponseWriter, r *http.Request) {
	username, _ := h.auth.GetUsername(r)

	if err := h.emailRepo.DeleteAll(); err != nil {
		log.Printf("Failed to wipe emails: %v", err)
		http.Error(w, "Failed to wipe emails", http.StatusInternalServerError)
		return
	}

	log.Printf("User %s wiped all emails", username)
	http.Redirect(w, r, "/emails?message=wiped", http.StatusSeeOther)
}

// MarkEmailRead marks an email as read
func (h *Handler) MarkEmailRead(w http.ResponseWriter, r *http.Request) {
	idStr := r.PathValue("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		http.Error(w, "Invalid email ID", http.StatusBadRequest)
		return
	}

	if err := h.emailRepo.UpdateStatus(id, "read"); err != nil {
		log.Printf("Failed to mark email as read: %v", err)
		http.Error(w, "Failed to update email", http.StatusInternalServerError)
		return
	}

	http.Redirect(w, r, "/emails/"+idStr, http.StatusSeeOther)
}

// renderTemplate renders a template with the given data
func (h *Handler) renderTemplate(w http.ResponseWriter, name string, data interface{}) {
	tmpl := parseTemplate(name)
	if err := tmpl.ExecuteTemplate(w, "base", data); err != nil {
		log.Printf("Template error: %v", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
	}
}
