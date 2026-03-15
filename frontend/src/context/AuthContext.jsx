import { createContext, useContext, useState, useEffect } from "react";
import { api, saveToken, clearToken, hasToken } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (hasToken()) {
      api.me()
        .then(setUser)
        .catch(() => clearToken())
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  async function login(email, password) {
    const { access_token } = await api.login({ email, password });
    saveToken(access_token);
    const me = await api.me();
    setUser(me);
    return me;
  }

  async function signup(data) {
    const { access_token } = await api.signup(data);
    saveToken(access_token);
    const me = await api.me();
    setUser(me);
    return me;
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
