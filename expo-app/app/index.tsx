import { useEffect, useRef, useCallback } from 'react'
import {
  View,
  Text,
  StyleSheet,
  Animated,
  Easing,
  Platform,
  useWindowDimensions,
} from 'react-native'
import { router } from 'expo-router'
import { Audio } from 'expo-av'

import {
  useFonts,
  DancingScript_700Bold,
} from '@expo-google-fonts/dancing-script'
import { useAuth } from '../contexts/AuthContext'

const LETTERS = 'FUTURES'.split('')
const STAGGER_MS = 70
const TOTAL_MS = 2500
const PARTICLE_COUNT = 8

export default function SplashScreen() {
  const { session, isLoading } = useAuth()
  const [fontsLoaded, fontError] = useFonts({ DancingScript_700Bold })
  const { width: W, height: H } = useWindowDimensions()
  const isLandscape = W > H
  const isDesktop = Platform.OS === 'web' && W >= 768

  const fadeAnim = useRef(new Animated.Value(0)).current
  const breatheAnim = useRef(new Animated.Value(1)).current
  const mottoAnim = useRef(new Animated.Value(0)).current
  const lDotAnim = useRef(new Animated.Value(0)).current
  const rDotAnim = useRef(new Animated.Value(0)).current
  const letterAnims = useRef(LETTERS.map(() => new Animated.Value(0))).current
  const particleAnims = useRef(
    Array.from({ length: PARTICLE_COUNT }, () => new Animated.Value(0))
  ).current
  const particlePositions = useRef(
    Array.from({ length: PARTICLE_COUNT }, () => ({
      left: 20 + Math.random() * 60,
      top: 35 + Math.random() * 30,
      delay: 1.2 + Math.random() * 1.5,
    }))
  ).current

  const animationComplete = useRef(false)
  const soundComplete = useRef(false)
  const navTimer = useRef<ReturnType<typeof setTimeout>>()
  const soundRef = useRef<Audio.Sound>()

  const tryNavigate = useCallback(() => {
    if (animationComplete.current && soundComplete.current) {
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 600,
        useNativeDriver: true,
      }).start(() => {
        if (session) router.replace('/broker-connect')
        else router.replace('/sign')
      })
    }
  }, [session, fadeAnim])

  const startBreathing = useCallback(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(breatheAnim, {
          toValue: 1.008,
          duration: 2500,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(breatheAnim, {
          toValue: 1,
          duration: 2500,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ])
    ).start()
  }, [breatheAnim])

  useEffect(() => {
    const ready = !isLoading && (fontsLoaded || fontError)
    if (!ready) return

    Audio.Sound.createAsync(
      require('../assets/audio/cashout.mp3'),
      { volume: 0.65, shouldPlay: true }
    ).then(({ sound }) => {
      soundRef.current = sound
      sound.setOnPlaybackStatusUpdate(status => {
        if (status.isLoaded && status.didJustFinish) {
          soundComplete.current = true
          tryNavigate()
        }
      })
    }).catch(() => {
      soundComplete.current = true
    })

    Animated.stagger(
      STAGGER_MS,
      letterAnims.map(a =>
        Animated.timing(a, {
          toValue: 1,
          duration: 280,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        })
      )
    ).start()

    Animated.sequence([
      Animated.delay(0),
      Animated.timing(lDotAnim, { toValue: 1, duration: 600, useNativeDriver: true }),
    ]).start()
    Animated.sequence([
      Animated.delay(100),
      Animated.timing(rDotAnim, { toValue: 1, duration: 600, useNativeDriver: true }),
    ]).start()
    particleAnims.forEach((a, i) => {
      Animated.sequence([
        Animated.delay(particlePositions[i].delay * 1000),
        Animated.timing(a, { toValue: 1, duration: 3000, useNativeDriver: true }),
      ]).start()
    })

    const motto = setTimeout(() => {
      Animated.timing(mottoAnim, { toValue: 1, duration: 600, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start()
    }, 900)

    const breath = setTimeout(startBreathing, 1500)
    navTimer.current = setTimeout(() => {
      animationComplete.current = true
      tryNavigate()
    }, TOTAL_MS)

    return () => {
      clearTimeout(motto)
      clearTimeout(breath)
      if (navTimer.current) clearTimeout(navTimer.current)
      soundRef.current?.unloadAsync()
    }
  }, [isLoading, fontsLoaded, fontError])

  if (isLoading || (!fontsLoaded && !fontError)) {
    return <View style={styles.container} />
  }

  const letterFontSize = isDesktop ? 96 : isLandscape ? 48 : W < 380 ? 40 : 56
  const mottoFontSize = isDesktop ? 15 : W < 380 ? 11 : 13
  const dotSize = isDesktop ? 4 : 3

  return (
    <Animated.View
      style={[
        styles.container,
        {
          opacity: fadeAnim.interpolate({
            inputRange: [0, 1],
            outputRange: [1, 0],
          }),
        },
      ]}
    >
      <View style={[styles.glow, { top: H * 0.1, left: W * 0.1, width: Math.min(W * 0.8, 700), height: H * 0.35, borderRadius: Math.min(W * 0.5, 400) }]} />

      <Animated.View
        style={[
          styles.dot,
          { width: dotSize, height: dotSize, borderRadius: dotSize / 2 },
          styles.dotLeft,
          {
            opacity: lDotAnim.interpolate({
              inputRange: [0, 0.5, 1],
              outputRange: [0, 1, 0],
            }),
            transform: [{
              scale: lDotAnim.interpolate({
                inputRange: [0, 0.5, 1],
                outputRange: [0.5, 1.2, 0],
              }),
            }],
          },
        ]}
      />
      <Animated.View
        style={[
          styles.dot,
          { width: dotSize, height: dotSize, borderRadius: dotSize / 2 },
          styles.dotRight,
          {
            opacity: rDotAnim.interpolate({
              inputRange: [0, 0.5, 1],
              outputRange: [0, 1, 0],
            }),
            transform: [{
              scale: rDotAnim.interpolate({
                inputRange: [0, 0.5, 1],
                outputRange: [0.5, 1.2, 0],
              }),
            }],
          },
        ]}
      />

      <Animated.View style={[styles.titleWrap, { transform: [{ scale: breatheAnim }] }]}>
        {LETTERS.map((letter, i) => (
          <Animated.Text
            key={i}
            style={[
              styles.letter,
              {
                fontSize: letterFontSize,
                opacity: letterAnims[i],
                transform: [
                  { scale: letterAnims[i].interpolate({ inputRange: [0, 1], outputRange: [0.85, 1] }) },
                  { translateY: letterAnims[i].interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) },
                ],
              },
            ]}
          >
            {letter}
          </Animated.Text>
        ))}
      </Animated.View>

      <Animated.View
        style={[
          styles.mottoWrap,
          {
            opacity: mottoAnim,
            transform: [{ translateY: mottoAnim.interpolate({ inputRange: [0, 1], outputRange: [20, 0] }) }],
          },
        ]}
      >
        <Text style={[styles.mottoText, { fontSize: mottoFontSize, letterSpacing: isDesktop ? 4 : 3 }]}>PRICE IS THE ONLY INDICATOR</Text>
      </Animated.View>
    </Animated.View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  glow: {
    position: 'absolute',
    backgroundColor: 'rgba(255,255,255,0.04)',
  },
  dot: {
    position: 'absolute',
    top: '38%',
    backgroundColor: '#fff',
  },
  dotLeft: { left: '25%' },
  dotRight: { right: '25%' },
  titleWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  letter: {
    fontFamily: 'DancingScript_700Bold',
    color: '#FFFFFF',
    textShadowColor: 'rgba(255,255,255,0.3)',
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 12,
  },
  mottoWrap: {
    marginTop: 40,
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderWidth: 1,
    borderColor: 'rgba(100,180,255,0.3)',
    borderRadius: 60,
    paddingVertical: 8,
    paddingHorizontal: 20,
  },
  mottoText: {
    color: '#bbddff',
    textTransform: 'uppercase',
  },
})
