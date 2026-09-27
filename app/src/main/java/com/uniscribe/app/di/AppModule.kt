package com.uniscribe.app.di

import com.uniscribe.app.BuildConfig
import com.uniscribe.app.network.HttpTranscriptionService
import com.uniscribe.app.network.TranscriptionService

/**
 * Small application container.
 *
 * A release build must inject a short-lived user/session token provider from
 * the real authentication layer. There is intentionally no shared build token
 * or Gemini credential in this default container.
 */
class AppContainer(
    authTokenProvider: () -> String? = { null },
    val transcriptionService: TranscriptionService = HttpTranscriptionService(
        configuredEndpoint = BuildConfig.UNISCRIBE_TRANSCRIPTION_URL,
        authTokenProvider = authTokenProvider,
    ),
)
