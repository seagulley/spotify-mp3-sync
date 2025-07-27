import { useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';

interface User {
  id: string;
  display_name: string;
  email?: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
}

export const useAuth = () => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    loading: true,
  });

  const BACKEND_URL = 'https://spotisync.loca.lt';

  useEffect(() => {
    loadStoredAuth();
  }, []);

  const loadStoredAuth = async () => {
    try {
      const token = await AsyncStorage.getItem('jwt_token');
      if (token) {
        // Verify token and get user info
        const user = await fetchUserProfile(token);
        setAuthState({ user, token, loading: false });
      } else {
        setAuthState({ user: null, token: null, loading: false });
      }
    } catch (error) {
      console.error('Error loading auth:', error);
      setAuthState({ user: null, token: null, loading: false });
    }
  };

  const fetchUserProfile = async (token: string): Promise<User | null> => {
    try {
      const response = await fetch(`${BACKEND_URL}/user/profile`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (response.ok) {
        const userData = await response.json();
        return {
          id: userData.id,
          display_name: userData.display_name,
          email: userData.email,
        };
      }
      return null;
    } catch (error) {
      console.error('Error fetching user profile:', error);
      return null;
    }
  };

  const login = async () => {
    try {
      // Start the OAuth flow by opening the login URL
      const result = await WebBrowser.openAuthSessionAsync(
        `${BACKEND_URL}/login`,
        `${Linking.createURL('/')}`
      );

      if (result.type === 'success' && result.url) {
        // Extract the JWT token from the URL
        const url = new URL(result.url);
        const token = url.searchParams.get('token');
        
        if (token) {
          // Store the token
          await AsyncStorage.setItem('jwt_token', token);
          
          // Fetch user profile
          const user = await fetchUserProfile(token);
          
          setAuthState({ user, token, loading: false });
          return true;
        }
      }
      return false;
    } catch (error) {
      console.error('Login error:', error);
      return false;
    }
  };

  const logout = async () => {
    try {
      await AsyncStorage.removeItem('jwt_token');
      setAuthState({ user: null, token: null, loading: false });
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  return {
    user: authState.user,
    token: authState.token,
    loading: authState.loading,
    login,
    logout,
    isAuthenticated: !!authState.token,
  };
}; 