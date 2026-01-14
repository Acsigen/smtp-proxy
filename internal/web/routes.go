package web

import (
	"net/http"

	"github.com/gorilla/sessions"

	"smtp-proxy/internal/config"
	"smtp-proxy/internal/database"
)

// Router manages HTTP route registration
type Router struct {
	handler *Handler
	auth    *AuthMiddleware
}

// NewRouter creates a new router with all dependencies
func NewRouter(cfg *config.Config, emailRepo *database.EmailRepository, userRepo *database.UserRepository, store *sessions.CookieStore) *Router {
	handler := NewHandler(cfg, emailRepo, userRepo, store)
	auth := NewAuthMiddleware(store, cfg.Web.SessionName)

	return &Router{
		handler: handler,
		auth:    auth,
	}
}

// RegisterRoutes registers all HTTP routes on the provided mux
func (r *Router) RegisterRoutes(mux *http.ServeMux) {
	// Public routes (no authentication required)
	mux.HandleFunc("GET /login", r.handler.LoginPage)
	mux.HandleFunc("POST /login", r.handler.LoginSubmit)
	mux.HandleFunc("POST /logout", r.handler.Logout)

	// Protected routes (wrapped with authentication middleware)
	mux.HandleFunc("GET /", r.auth.RequireAuth(r.handleRoot))
	mux.HandleFunc("GET /emails", r.auth.RequireAuth(r.handler.EmailList))
	mux.HandleFunc("GET /emails/{id}", r.auth.RequireAuth(r.handler.EmailDetail))
	mux.HandleFunc("POST /emails/wipe", r.auth.RequireAuth(r.handler.WipeEmails))
	mux.HandleFunc("POST /emails/{id}/mark-read", r.auth.RequireAuth(r.handler.MarkEmailRead))
}

// handleRoot redirects the root path to the emails list
func (r *Router) handleRoot(w http.ResponseWriter, req *http.Request) {
	http.Redirect(w, req, "/emails", http.StatusSeeOther)
}
