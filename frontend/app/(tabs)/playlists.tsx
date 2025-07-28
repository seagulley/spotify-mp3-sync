import { StyleSheet, TouchableOpacity, Alert, FlatList } from 'react-native';
import { useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { ThemedText } from '@/components/ThemedText';
import { ThemedView } from '@/components/ThemedView';

interface Playlist {
  id: string;
  name: string;
  track_count?: number;
}

export default function PlaylistsScreen() {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);

  const BACKEND_URL = 'https://spotisync.loca.lt';

  useEffect(() => {
    loadAuthAndPlaylists();
  }, []);

  const loadAuthAndPlaylists = async () => {
    try {
      const storedToken = await AsyncStorage.getItem('jwt_token');
      if (storedToken) {
        setToken(storedToken);
        await fetchUserPlaylists(storedToken);
      } else {
        Alert.alert('Not Logged In', 'Please log in to view your playlists.');
      }
    } catch (error) {
      console.error('Error loading playlists:', error);
      Alert.alert('Error', 'Failed to load playlists.');
    } finally {
      setLoading(false);
    }
  };

  const fetchUserPlaylists = async (authToken: string) => {
    try {
      const response = await fetch(`${BACKEND_URL}/playlists`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });
      
      if (response.ok) {
        const playlistsData = await response.json();
        setPlaylists(playlistsData.playlists || []);
      } else {
        console.error('Failed to fetch playlists:', response.status);
        Alert.alert('Error', 'Failed to load playlists.');
      }
    } catch (error) {
      console.error('Error fetching playlists:', error);
      Alert.alert('Error', 'Failed to load playlists.');
    }
  };

  const handlePlaylistPress = (playlist: Playlist) => {
    Alert.alert('Playlist', `Selected: ${playlist.name}`);
    // TODO: Navigate to playlist details page
  };

  const renderPlaylist = ({ item }: { item: Playlist }) => (
    <TouchableOpacity 
      style={styles.playlistItem}
      onPress={() => handlePlaylistPress(item)}
    >
      <ThemedView style={styles.playlistInfo}>
        <ThemedText style={styles.playlistName}>{item.name}</ThemedText>
        {item.track_count && (
          <ThemedText style={styles.trackCount}>
            {item.track_count} track{item.track_count !== 1 ? 's' : ''}
          </ThemedText>
        )}
      </ThemedView>
      <ThemedText style={styles.playlistArrow}>→</ThemedText>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <ThemedView style={styles.container}>
        <ThemedText type="title">Loading playlists...</ThemedText>
      </ThemedView>
    );
  }

  if (!token) {
    return (
      <ThemedView style={styles.container}>
        <ThemedText type="title">Please log in to view your playlists</ThemedText>
      </ThemedView>
    );
  }

  return (
    <ThemedView style={styles.container}>
      <ThemedText type="title">My Playlists</ThemedText>
      <ThemedText style={styles.subtitle}>
        {playlists.length} playlist{playlists.length !== 1 ? 's' : ''} found
      </ThemedText>
      
      {playlists.length === 0 ? (
        <ThemedView style={styles.emptyState}>
          <ThemedText style={styles.emptyText}>
            No playlists found. Make sure you're logged in with Spotify.
          </ThemedText>
        </ThemedView>
      ) : (
        <FlatList
          data={playlists}
          renderItem={renderPlaylist}
          keyExtractor={(item) => item.id}
          style={styles.playlistList}
          showsVerticalScrollIndicator={false}
        />
      )}
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
  },
  subtitle: {
    fontSize: 16,
    marginBottom: 16,
    opacity: 0.7,
  },
  playlistList: {
    flex: 1,
  },
  playlistItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    marginBottom: 8,
    borderRadius: 8,
    backgroundColor: 'rgba(161, 206, 220, 0.1)',
  },
  playlistInfo: {
    flex: 1,
  },
  playlistName: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  trackCount: {
    fontSize: 14,
    opacity: 0.7,
  },
  playlistArrow: {
    fontSize: 18,
    opacity: 0.6,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  emptyText: {
    textAlign: 'center',
    fontSize: 16,
    opacity: 0.7,
    lineHeight: 24,
  },
}); 