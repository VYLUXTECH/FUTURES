import { Tabs } from 'expo-router'
import { Text, Platform } from 'react-native'
import { useTheme } from '../../contexts/ThemeContext'

function TabIcon({ emoji }: { emoji: string }) {
  return <Text style={{ fontSize: 22 }}>{emoji}</Text>
}

export default function TabLayout() {
  const { colors } = useTheme()
  const isWeb = Platform.OS === 'web'
  const isDesktop = isWeb && typeof window !== 'undefined' && window.innerWidth >= 768

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarPosition: 'bottom',
        tabBarStyle: {
          backgroundColor: colors.card,
          borderTopColor: colors.cardBorder,
          borderTopWidth: 1,
          paddingBottom: isDesktop ? 12 : 8,
          paddingTop: 8,
          height: isDesktop ? 60 : 70,
          maxWidth: isDesktop ? 960 : undefined,
          alignSelf: isDesktop ? 'center' : undefined,
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarLabelStyle: {
          fontSize: isDesktop ? 13 : 11,
          fontWeight: '600',
        },
        tabBarItemStyle: {
          paddingVertical: isDesktop ? 8 : 4,
        },
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          title: 'Dashboard',
          tabBarLabel: 'Dashboard',
          tabBarIcon: () => <TabIcon emoji="📊" />,
        }}
      />
      <Tabs.Screen
        name="copilot"
        options={{
          title: 'Copilot',
          tabBarLabel: 'Copilot',
          tabBarIcon: () => <TabIcon emoji="🤖" />,
        }}
      />
      <Tabs.Screen
        name="accountability"
        options={{
          title: 'History',
          tabBarLabel: 'History',
          tabBarIcon: () => <TabIcon emoji="📜" />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarLabel: 'Settings',
          tabBarIcon: () => <TabIcon emoji="⚙️" />,
        }}
      />
      <Tabs.Screen
        name="support"
        options={{
          title: 'Support',
          tabBarLabel: 'Support',
          tabBarIcon: () => <TabIcon emoji="💬" />,
        }}
      />
    </Tabs>
  )
}
