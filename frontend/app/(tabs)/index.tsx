import { Image } from 'expo-image';
import { Platform, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';

import { HelloWave } from '@/components/HelloWave';
import ParallaxScrollView from '@/components/ParallaxScrollView';
import { ThemedText } from '@/components/ThemedText';
import { ThemedView } from '@/components/ThemedView';

interface User {
  id: string;
  display_name: string;
  email?: string;
}

export default function HomeScreen() {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const BACKEND_URL = 'https://purple-eyes-laugh.loca.lt';

  useEffect(() => {
    loadStoredAuth();
  }, []);

  const loadStoredAuth = async () => {
    try {
      const storedToken = await AsyncStorage.getItem('jwt_token');
      if (storedToken) {
        const userProfile = await fetchUserProfile(storedToken);
        setUser(userProfile);
        setToken(storedToken);
      }
    } catch (error) {
      console.error('Error loading auth:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserProfile = async (authToken: string): Promise<User | null> => {
    try {
      const response = await fetch(`${BACKEND_URL}/user/profile`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
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

  const handleLogin = async () => {
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
          const userProfile = await fetchUserProfile(authToken);
          setUser(userProfile);
          setToken(authToken);
          Alert.alert('Success', 'Successfully logged in!');
        }
      }
    } catch (error) {
      console.error('Login error:', error);
      Alert.alert('Error', 'Failed to login. Please try again.');
    }
  };

  const handleLogout = async () => {
    try {
      await AsyncStorage.removeItem('jwt_token');
      setUser(null);
      setToken(null);
      Alert.alert('Success', 'Successfully logged out!');
    } catch (error) {
      console.error('Logout error:', error);
      Alert.alert('Error', 'Failed to logout. Please try again.');
    }
  };

  if (loading) {
    return (
      <ThemedView style={styles.container}>
        <ThemedText type="title">Loading...</ThemedText>
      </ThemedView>
    );
  }

  return (
    <ParallaxScrollView
      headerBackgroundColor={{ light: '#A1CEDC', dark: '#1D3D47' }}
      headerImage={
        <Image
          source={require('@/assets/images/partial-react-logo.png')}
          style={styles.reactLogo}
        />
      }>
      <ThemedView style={styles.titleContainer}>
        <ThemedText type="title">Spotify MP3 Sync</ThemedText>
        <HelloWave />
      </ThemedView>

      {user ? (
        <ThemedView style={styles.authContainer}>
          <ThemedText type="subtitle">Welcome, {user.display_name}!</ThemedText>
          {user.email && (
            <ThemedText>Email: {user.email}</ThemedText>
          )}
          <TouchableOpacity style={styles.button} onPress={handleLogout}>
            <ThemedText style={styles.buttonText}>Log Out</ThemedText>
          </TouchableOpacity>
        </ThemedView>
      ) : (
        <ThemedView style={styles.authContainer}>
          <ThemedText type="subtitle">Login with Spotify</ThemedText>
          <ThemedText>
            Connect your Spotify account to start syncing your playlists and downloading MP3s.
          </ThemedText>
          <TouchableOpacity style={styles.button} onPress={handleLogin}>
            <ThemedText style={styles.buttonText}>Login with Spotify</ThemedText>
          </TouchableOpacity>
        </ThemedView>
      )}

      <ThemedView style={styles.stepContainer}>
        <ThemedText type="subtitle">How it works</ThemedText>
        <ThemedText>
          1. Login with your Spotify account{'\n'}
          2. Browse your playlists{'\n'}
          3. Download your favorite songs as MP3s{'\n'}
          4. Manage your downloaded music library
        </ThemedText>
      </ThemedView>
    </ParallaxScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  titleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  authContainer: {
    gap: 16,
    marginBottom: 16,
    padding: 16,
    borderRadius: 8,
    backgroundColor: 'rgba(161, 206, 220, 0.1)',
  },
  stepContainer: {
    gap: 8,
    marginBottom: 8,
  },
  button: {
    backgroundColor: '#1DB954',
    padding: 12,
    borderRadius: 6,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonText: {
    color: 'white',
    fontWeight: 'bold',
    fontSize: 16,
  },
  reactLogo: {
    height: 178,
    width: 290,
    bottom: 0,
    left: 0,
    position: 'absolute',
  },
});
