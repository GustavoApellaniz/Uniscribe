package com.uniscribe.app

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.uniscribe.app.audio.CacheAudioRecorder
import com.uniscribe.app.network.BackendConfigurationException
import com.uniscribe.app.network.BackendUnavailableException
import com.uniscribe.app.network.TranscriptionResult
import com.uniscribe.app.network.TranscriptionService
import java.io.File
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.util.Locale
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.RejectedExecutionException

/**
 * Small native Android client for the UniScribe MVP.
 *
 * The activity deliberately uses platform Views instead of Compose so the
 * project can build without a UI dependency. The Python backend is configured
 * at build time with -PUNISCRIBE_TRANSCRIPTION_URL=...; no provider key is
 * stored in the APK.
 */
class MainActivity : Activity() {
    private lateinit var statusText: TextView
    private lateinit var detailText: TextView
    private lateinit var summaryText: TextView
    private lateinit var messageText: TextView
    private lateinit var startButton: Button
    private lateinit var stopButton: Button
    private lateinit var copyButton: Button
    private lateinit var exportButton: Button

    private val audioRecorder: CacheAudioRecorder by lazy { CacheAudioRecorder(applicationContext) }
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private var state = State.IDLE
    private var startedAt = 0L
    private var currentSummary = ""
    private var disclosureShown = false
    private val consentPreferences by lazy { getPreferences(MODE_PRIVATE) }

    private val ticker = object : Runnable {
        override fun run() {
            if (state != State.RECORDING) return
            statusText.text = getString(
                R.string.recording_elapsed,
                formatElapsed(SystemClock.elapsedRealtime() - startedAt),
            )
            mainHandler.postDelayed(this, TICK_MILLIS)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        disclosureShown = consentPreferences.getInt(CONSENT_KEY, 0) >= CONSENT_VERSION
        buildUi()
        renderIdle()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQUEST_RECORD_AUDIO) return
        if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            startRecording()
        } else {
            renderIdle()
            showMessage(getString(R.string.permission_denied), true)
        }
    }

    @Deprecated("The platform activity result API is used to keep the app dependency-free")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_EXPORT && resultCode == RESULT_OK) {
            data?.data?.let(::writeExport)
        }
    }

    override fun onStop() {
        // Background capture is intentionally not advertised by the MVP. Avoid
        // silently continuing to record when the user leaves the activity.
        if (state == State.RECORDING) {
            stopTicker()
            audioRecorder.cancel()
            state = State.IDLE
            renderIdle()
        }
        super.onStop()
    }

    override fun onDestroy() {
        stopTicker()
        if (audioRecorder.isRecording) audioRecorder.cancel()
        executor.shutdownNow()
        super.onDestroy()
    }

    private fun buildUi() {
        val scroll = ScrollView(this).apply {
            isFillViewport = true
            setBackgroundColor(getColor(R.color.background))
        }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(28), dp(24), dp(28))
        }
        content.addView(TextView(this).apply {
            text = getString(R.string.app_name)
            setTextColor(getColor(R.color.text_primary))
            textSize = 30f
            setTypeface(typeface, Typeface.BOLD)
        }, matchWidth())
        content.addView(TextView(this).apply {
            text = getString(R.string.app_subtitle)
            setTextColor(getColor(R.color.text_secondary))
            textSize = 16f
            setPadding(0, dp(6), 0, dp(24))
        }, matchWidth())
        statusText = TextView(this).apply {
            setTextColor(getColor(R.color.primary_dark))
            textSize = 22f
            setTypeface(typeface, Typeface.BOLD)
            gravity = Gravity.CENTER_VERTICAL
            minHeight = dp(56)
        }
        content.addView(statusText, matchWidth())
        detailText = TextView(this).apply {
            setTextColor(getColor(R.color.text_secondary))
            textSize = 14f
            setPadding(0, dp(4), 0, dp(18))
        }
        content.addView(detailText, matchWidth())
        val controls = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        startButton = Button(this).apply {
            text = getString(R.string.start_listening)
            isAllCaps = false
            setOnClickListener { onStartClicked() }
        }
        stopButton = Button(this).apply {
            text = getString(R.string.stop)
            isAllCaps = false
            setOnClickListener { onStopClicked() }
        }
        controls.addView(startButton, weightedParams())
        controls.addView(stopButton, weightedParams(dp(12)))
        content.addView(controls, matchWidth())
        content.addView(TextView(this).apply {
            text = getString(R.string.summary)
            setTextColor(getColor(R.color.text_primary))
            textSize = 18f
            setTypeface(typeface, Typeface.BOLD)
            setPadding(0, dp(28), 0, dp(8))
        }, matchWidth())
        summaryText = TextView(this).apply {
            setTextColor(getColor(R.color.text_primary))
            textSize = 16f
            gravity = Gravity.TOP or Gravity.START
            isTextSelectable = true
            minHeight = dp(140)
            setPadding(dp(14), dp(14), dp(14), dp(14))
            setBackgroundColor(getColor(R.color.surface))
        }
        content.addView(summaryText, matchWidth())
        val actions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(16), 0, dp(8))
        }
        copyButton = Button(this).apply {
            text = getString(R.string.copy)
            isAllCaps = false
            setOnClickListener { copySummary() }
        }
        exportButton = Button(this).apply {
            text = getString(R.string.export)
            isAllCaps = false
            setOnClickListener { exportSummary() }
        }
        actions.addView(copyButton, weightedParams())
        actions.addView(exportButton, weightedParams(dp(12)))
        content.addView(actions, matchWidth())
        messageText = TextView(this).apply {
            textSize = 14f
            visibility = View.GONE
        }
        content.addView(messageText, matchWidth())
        scroll.addView(content, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        setContentView(scroll)
    }

    private fun onStartClicked() {
        if (state != State.IDLE && state != State.COMPLETE) return
        if (!disclosureShown) {
            showRecordingDisclosure()
            return
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), REQUEST_RECORD_AUDIO)
            return
        }
        startRecording()
    }

    /** Prominent, affirmative disclosure required before microphone access. */
    private fun showRecordingDisclosure() {
        AlertDialog.Builder(this)
            .setTitle(R.string.recording_disclosure_title)
            .setMessage(R.string.recording_disclosure_message)
            .setNegativeButton(R.string.cancel, null)
            .setPositiveButton(R.string.continue_label) { _, _ ->
                disclosureShown = true
                consentPreferences.edit().putInt(CONSENT_KEY, CONSENT_VERSION).apply()
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    startRecording()
                } else {
                    requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), REQUEST_RECORD_AUDIO)
                }
            }
            .show()
    }

    private fun startRecording() {
        if (state == State.RECORDING || state == State.PROCESSING) return
        currentSummary = ""
        summaryText.setText(R.string.summary_empty)
        clearMessage()
        try {
            audioRecorder.start()
            startedAt = SystemClock.elapsedRealtime()
            renderRecording()
            mainHandler.post(ticker)
        } catch (_: Exception) {
            audioRecorder.cancel()
            renderIdle()
            showMessage(getString(R.string.recording_error), true)
        }
    }

    private fun onStopClicked() {
        if (state != State.RECORDING) return
        stopTicker()
        val file = try {
            audioRecorder.stop()
        } catch (_: Exception) {
            renderIdle()
            showMessage(getString(R.string.recording_error), true)
            return
        }
        renderProcessing()
        submit(file)
    }

    private fun submit(file: File) {
        val service: TranscriptionService = (application as UniScribeApplication).container.transcriptionService
        try {
            executor.execute {
                try {
                    val result = service.transcribe(file)
                    mainHandler.post { if (!isFinishing && !isDestroyed) renderResult(result) }
                } catch (error: Exception) {
                    mainHandler.post { if (!isFinishing && !isDestroyed) renderError(messageFor(error)) }
                } finally {
                    file.delete()
                }
            }
        } catch (_: RejectedExecutionException) {
            file.delete()
            renderError(getString(R.string.processing_error))
        }
    }

    private fun renderIdle() {
        state = State.IDLE
        statusText.setText(R.string.ready)
        detailText.text = ""
        startButton.isEnabled = true
        stopButton.isEnabled = false
        copyButton.isEnabled = false
        exportButton.isEnabled = false
    }

    private fun renderRecording() {
        state = State.RECORDING
        statusText.text = getString(R.string.recording_elapsed, formatElapsed(0))
        detailText.setText(R.string.recording)
        startButton.isEnabled = false
        stopButton.isEnabled = true
        copyButton.isEnabled = false
        exportButton.isEnabled = false
    }

    private fun renderProcessing() {
        state = State.PROCESSING
        statusText.setText(R.string.processing)
        detailText.setText(R.string.processing_detail)
        startButton.isEnabled = false
        stopButton.isEnabled = false
        copyButton.isEnabled = false
        exportButton.isEnabled = false
    }

    private fun renderResult(result: TranscriptionResult) {
        val text = result.summary.ifBlank { result.transcript }.trim()
        if (text.isEmpty()) {
            renderError(getString(R.string.empty_response))
            return
        }
        state = State.COMPLETE
        currentSummary = text
        summaryText.text = text
        statusText.setText(R.string.summary_ready)
        detailText.text = ""
        startButton.isEnabled = true
        stopButton.isEnabled = false
        copyButton.isEnabled = true
        exportButton.isEnabled = true
    }

    private fun renderError(message: String) {
        renderIdle()
        summaryText.setText(R.string.summary_empty)
        showMessage(message, true)
    }

    private fun copySummary() {
        if (currentSummary.isBlank()) return
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
        if (clipboard == null) {
            showMessage(getString(R.string.export_error), true)
            return
        }
        clipboard.setPrimaryClip(ClipData.newPlainText(getString(R.string.summary), currentSummary))
        showMessage(getString(R.string.copied), false)
    }

    private fun exportSummary() {
        if (currentSummary.isBlank()) return
        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = getString(R.string.export_mime_type)
            putExtra(Intent.EXTRA_TITLE, getString(R.string.export_file_name))
        }
        @Suppress("DEPRECATION")
        startActivityForResult(intent, REQUEST_EXPORT)
    }

    private fun writeExport(uri: Uri) {
        try {
            contentResolver.openOutputStream(uri)?.use { it.write(currentSummary.toByteArray(Charsets.UTF_8)) }
                ?: error("unavailable")
            showMessage(getString(R.string.export_success), false)
        } catch (_: Exception) {
            showMessage(getString(R.string.export_error), true)
        }
    }

    private fun showMessage(message: String, error: Boolean) {
        messageText.text = message
        messageText.setTextColor(getColor(if (error) R.color.error else R.color.success))
        messageText.visibility = View.VISIBLE
    }

    private fun clearMessage() {
        messageText.text = ""
        messageText.visibility = View.GONE
    }

    private fun messageFor(error: Throwable): String {
        val chain = generateSequence(error) { it.cause }.take(6).toList()
        return when {
            chain.any { it is BackendConfigurationException } -> getString(R.string.configuration_error)
            chain.any {
                it is BackendUnavailableException || it is UnknownHostException ||
                    it is ConnectException || it is SocketTimeoutException
            } -> getString(R.string.offline_error)
            else -> getString(R.string.processing_error)
        }
    }

    private fun stopTicker() = mainHandler.removeCallbacks(ticker)
    private fun formatElapsed(millis: Long): String {
        val seconds = (millis / 1000L).coerceAtLeast(0L)
        return String.format(Locale.getDefault(), "%02d:%02d", seconds / 60L, seconds % 60L)
    }
    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
    private fun matchWidth() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT,
    )
    private fun weightedParams(marginStart: Int = 0) = LinearLayout.LayoutParams(0, dp(52), 1f).apply {
        this.marginStart = marginStart
    }

    private enum class State { IDLE, RECORDING, PROCESSING, COMPLETE }

    private companion object {
        const val REQUEST_RECORD_AUDIO = 1001
        const val REQUEST_EXPORT = 1002
        const val TICK_MILLIS = 500L
        const val CONSENT_KEY = "recording_consent_version"
        const val CONSENT_VERSION = 1
    }
}
