import { StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';
import { router } from 'expo-router';

import { ThemedText } from '@/components/ThemedText';
import { ThemedView } from '@/components/ThemedView';

export default function LoginScreen() {
  const [loading, setLoading] = useState(false);

  const BACKEND_URL = 'https://spotisync.loca.lt';

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const storedToken = await AsyncStorage.getItem('jwt_token');
      if (storedToken) {
        // User is already logged in, redirect to main app
        router.replace('/(tabs)');
      }
    } catch (error) {
      console.error('Error checking auth status:', error);
    }
  };

  const handleLogin = async () => {
    setLoading(true);
    try {
      const result = await WebBrowser.openAuthSessionAsync(
        `${BACKEND_URL}/login`,
        `${Linking.createURL('/')}`
      );

      if (result.type === 'success' && result.url) {
        const url = new URL(result.url);
        const authToken = url.searchParams.get('token');
        
        if (authToken) {
          await AsyncStorage.setItem('jwt_token', authToken);
          // Immediately redirect to main app without showing alert
          router.replace('/(tabs)');
        }
      }
    } catch (error) {
      console.error('Login error:', error);
      Alert.alert('Error', 'Failed to login. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ThemedView style={styles.container}>
      <ThemedView style={styles.content}>
        <ThemedText type="title" style={styles.title}>
          Spotify MP3 Sync
        </ThemedText>
        
        <ThemedText style={styles.subtitle}>
          Download your Spotify playlists as MP3s for offline listening
        </ThemedText>

        <ThemedView style={styles.features}>
          <ThemedText style={styles.feature}>🎵 Sync your Spotify playlists</ThemedText>
          <ThemedText style={styles.feature}>📱 Download MP3s for offline use</ThemedText>
          <ThemedText style={styles.feature}>☁️ Store in the cloud</ThemedText>
        </ThemedView>

        <TouchableOpacity 
          style={[styles.loginButton, loading && styles.loginButtonDisabled]} 
          onPress={handleLogin}
          disabled={loading}
        >
          <ThemedText style={styles.loginButtonText}>
            {loading ? 'Logging in...' : 'Login with Spotify'}
          </ThemedText>
        </TouchableOpacity>
      </ThemedView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  content: {
    alignItems: 'center',
    maxWidth: 400,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    marginBottom: 16,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 18,
    textAlign: 'center',
    marginBottom: 32,
    opacity: 0.8,
    lineHeight: 24,
  },
  features: {
    marginBottom: 40,
    alignItems: 'center',
  },
  feature: {
    fontSize: 16,
    marginBottom: 8,
    opacity: 0.9,
  },
  loginButton: {
    backgroundColor: '#1DB954',
    paddingHorizontal: 32,
    paddingVertical: 16,
    borderRadius: 8,
    minWidth: 200,
  },
  loginButtonDisabled: {
    opacity: 0.6,
  },
  loginButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold',
    textAlign: 'center',
  },
}); 