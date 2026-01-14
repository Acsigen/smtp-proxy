package web

import (
	"log"
	"net/http"

	"github.com/gorilla/sessions"
)

// AuthMiddleware handles authentication checks for protected routes
type AuthMiddleware struct {
	store       *sessions.CookieStore
	sessionName string
}

// NewAuthMiddleware creates a new authentication middleware
func NewAuthMiddleware(store *sessions.CookieStore, sessionName string) *AuthMiddleware {
	return &AuthMiddleware{
		store:       store,
		sessionName: sessionName,
	}
}

// RequireAuth wraps a handler with authentication check
// Returns a named handler function via authWrapper struct to avoid anonymous functions
func (m *AuthMiddleware) RequireAuth(next http.HandlerFunc) http.HandlerFunc {
	wrapper := &authWrapper{
		middleware: m,
		next:       next,
	}
	return wrapper.ServeHTTP
}

// authWrapper is a named struct that wraps authentication logic
// This approach avoids anonymous functions for better code maintainability
type authWrapper struct {
	middleware *AuthMiddleware
	next       http.HandlerFunc
}

// ServeHTTP implements http.HandlerFunc for the auth wrapper
func (w *authWrapper) ServeHTTP(rw http.ResponseWriter, r *http.Request) {
	session, err := w.middleware.store.Get(r, w.middleware.sessionName)
	if err != nil {
		log.Printf("DEBUG: Auth middleware - session get error: %v", err)
		http.Redirect(rw, r, "/login", http.StatusSeeOther)
		return
	}

	userID, ok := session.Values["user_id"]
	if !ok || userID == nil {
		log.Printf("DEBUG: Auth middleware - user_id not found in session. Values: %v, IsNew: %v", session.Values, session.IsNew)
		http.Redirect(rw, r, "/login", http.StatusSeeOther)
		return
	}

	log.Printf("DEBUG: Auth middleware - user_id found: %v (type: %T)", userID, userID)
	w.next(rw, r)
}

// GetUserID retrieves the user ID from the session
func (m *AuthMiddleware) GetUserID(r *http.Request) (int64, bool) {
	session, err := m.store.Get(r, m.sessionName)
	if err != nil {
		return 0, false
	}

	userID, ok := session.Values["user_id"]
	if !ok {
		return 0, false
	}

	id, ok := userID.(int64)
	return id, ok
}

// GetUsername retrieves the username from the session
func (m *AuthMiddleware) GetUsername(r *http.Request) (string, bool) {
	session, err := m.store.Get(r, m.sessionName)
	if err != nil {
		return "", false
	}

	username, ok := session.Values["username"]
	if !ok {
		return "", false
	}

	name, ok := username.(string)
	return name, ok
}
