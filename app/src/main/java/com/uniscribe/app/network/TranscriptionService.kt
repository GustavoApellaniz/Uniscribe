package com.uniscribe.app.network

import java.io.File
import java.io.IOException

/**
 * Boundary between the UI and the transcription backend.
 *
 * The Android app does not contain provider credentials or a guessed endpoint.
 * A deployment can inject an HTTP implementation or another implementation of
 * this interface through the application container.
 */
interface TranscriptionService {
    @Throws(IOException::class)
    fun transcribe(audioFile: File): TranscriptionResult
}

data class TranscriptionResult(
    val transcript: String,
    val summary: String = ""
)
