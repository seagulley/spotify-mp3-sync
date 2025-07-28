import { StyleSheet, TouchableOpacity, Alert, FlatList } from 'react-native';
import { useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { ThemedText } from '@/components/ThemedText';
import { ThemedView } from '@/components/ThemedView';

interface Song {
  id: string;
  title: string;
  artist: string;
  album?: string;
  duration?: number;
  url?: string;
}

export default function SongsScreen() {
  const [songs, setSongs] = useState<Song[]>([]);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);

  const BACKEND_URL = 'https://spotisync.loca.lt';

  useEffect(() => {
    loadAuthAndSongs();
  }, []);

  const loadAuthAndSongs = async () => {
    try {
      const storedToken = await AsyncStorage.getItem('jwt_token');
      if (storedToken) {
        setToken(storedToken);
        await fetchUserSongs(storedToken);
      } else {
        Alert.alert('Not Logged In', 'Please log in to view your songs.');
      }
    } catch (error) {
      console.error('Error loading songs:', error);
      Alert.alert('Error', 'Failed to load songs.');
    } finally {
      setLoading(false);
    }
  };

  const fetchUserSongs = async (authToken: string) => {
    try {
      const response = await fetch(`${BACKEND_URL}/my-songs/search`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });
      
      if (response.ok) {
        const songsData = await response.json();
        setSongs(songsData.songs || []);
      } else {
        console.error('Failed to fetch songs:', response.status);
      }
    } catch (error) {
      console.error('Error fetching songs:', error);
    }
  };

  const handlePlaySong = (song: Song) => {
    if (song.url) {
      Alert.alert('Play Song', `Playing: ${song.title} by ${song.artist}`);
      // TODO: Implement actual audio playback
    } else {
      Alert.alert('No URL', 'This song is not available for playback.');
    }
  };

  const handleDeleteSong = async (songId: string) => {
    if (!token) return;

    try {
      const response = await fetch(`${BACKEND_URL}/song/${songId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        setSongs(songs.filter(song => song.id !== songId));
        Alert.alert('Success', 'Song deleted successfully!');
      } else {
        Alert.alert('Error', 'Failed to delete song.');
      }
    } catch (error) {
      console.error('Error deleting song:', error);
      Alert.alert('Error', 'Failed to delete song.');
    }
  };

  const renderSong = ({ item }: { item: Song }) => (
    <ThemedView style={styles.songItem}>
      <ThemedView style={styles.songInfo}>
        <ThemedText style={styles.songTitle}>{item.title}</ThemedText>
        <ThemedText style={styles.songArtist}>{item.artist}</ThemedText>
        {item.album && (
          <ThemedText style={styles.songAlbum}>{item.album}</ThemedText>
        )}
      </ThemedView>
      <ThemedView style={styles.songActions}>
        <TouchableOpacity 
          style={[styles.actionButton, styles.playButton]} 
          onPress={() => handlePlaySong(item)}
        >
          <ThemedText style={styles.buttonText}>Play</ThemedText>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.actionButton, styles.deleteButton]} 
          onPress={() => handleDeleteSong(item.id)}
        >
          <ThemedText style={styles.buttonText}>Delete</ThemedText>
        </TouchableOpacity>
      </ThemedView>
    </ThemedView>
  );

  if (loading) {
    return (
      <ThemedView style={styles.container}>
        <ThemedText type="title">Loading songs...</ThemedText>
      </ThemedView>
    );
  }

  if (!token) {
    return (
      <ThemedView style={styles.container}>
        <ThemedText type="title">Please log in to view your songs</ThemedText>
      </ThemedView>
    );
  }

  return (
    <ThemedView style={styles.container}>
      <ThemedText type="title">My Songs</ThemedText>
      <ThemedText style={styles.subtitle}>
        {songs.length} song{songs.length !== 1 ? 's' : ''} in your library
      </ThemedText>
      
      {songs.length === 0 ? (
        <ThemedView style={styles.emptyState}>
          <ThemedText style={styles.emptyText}>
            No songs yet! Download some songs from your playlists to see them here.
          </ThemedText>
        </ThemedView>
      ) : (
        <FlatList
          data={songs}
          renderItem={renderSong}
          keyExtractor={(item) => item.id}
          style={styles.songList}
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
  songList: {
    flex: 1,
  },
  songItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    marginBottom: 8,
    borderRadius: 8,
    backgroundColor: 'rgba(161, 206, 220, 0.1)',
  },
  songInfo: {
    flex: 1,
  },
  songTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  songArtist: {
    fontSize: 14,
    opacity: 0.8,
    marginBottom: 2,
  },
  songAlbum: {
    fontSize: 12,
    opacity: 0.6,
  },
  songActions: {
    flexDirection: 'row',
    gap: 8,
  },
  actionButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 4,
  },
  playButton: {
    backgroundColor: '#1DB954',
  },
  deleteButton: {
    backgroundColor: '#E74C3C',
  },
  buttonText: {
    color: 'white',
    fontSize: 12,
    fontWeight: 'bold',
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