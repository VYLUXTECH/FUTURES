import { useState } from 'react'
import { View, TextInput, TouchableOpacity, StyleSheet, type TextInputProps } from 'react-native'
import { ThemedText } from './ThemedText'
import { useTheme } from '../contexts/ThemeContext'
import { BorderRadius } from '../constants/theme'

type PasswordInputProps = TextInputProps & {
  inputStyle?: any
}

export function PasswordInput({ style, inputStyle, ...props }: PasswordInputProps) {
  const [show, setShow] = useState(false)
  const { colors } = useTheme()

  return (
    <View style={[styles.wrapper, style]}>
      <TextInput
        {...props}
        secureTextEntry={!show}
        style={[styles.input, { backgroundColor: colors.inputBg, color: colors.text, borderColor: colors.border, paddingRight: 48 }, inputStyle]}
      />
      <TouchableOpacity onPress={() => setShow(!show)} style={styles.eyeBtn}>
        <ThemedText style={{ fontSize: 18, opacity: 0.6 }}>
          {show ? '👁' : '👁‍🗨'}
        </ThemedText>
      </TouchableOpacity>
    </View>
  )
}

const styles = StyleSheet.create({
  wrapper: { position: 'relative' },
  input: { height: 50, borderWidth: 1, borderRadius: BorderRadius.md, paddingHorizontal: 14, fontSize: 15 },
  eyeBtn: { position: 'absolute', right: 12, top: 0, bottom: 0, justifyContent: 'center', paddingLeft: 8 },
})
