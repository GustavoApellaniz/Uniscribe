package com.uniscribe.app.audio

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import java.io.File
import java.io.IOException

/** Records a short lecture file into the app cache and owns its lifecycle. */
class CacheAudioRecorder(context: Context) {

    private val appContext = context.applicationContext
    private var mediaRecorder: MediaRecorder? = null
    private var outputFile: File? = null

    val isRecording: Boolean
        @Synchronized get() = mediaRecorder != null

    @Synchronized
    fun start(): File {
        check(mediaRecorder == null) { "A recording is already in progress." }

        val recordingsDirectory = File(appContext.cacheDir, RECORDINGS_DIRECTORY)
        if (!recordingsDirectory.exists() && !recordingsDirectory.mkdirs()) {
            throw IOException("Could not create the recording cache directory.")
        }

        val file = File.createTempFile("lecture_", ".m4a", recordingsDirectory)
        val recorder = createMediaRecorder()
        try {
            recorder.setAudioSource(MediaRecorder.AudioSource.MIC)
            recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            recorder.setAudioEncodingBitRate(AUDIO_BIT_RATE)
            recorder.setAudioSamplingRate(AUDIO_SAMPLE_RATE)
            recorder.setOutputFile(file.absolutePath)
            recorder.prepare()
            recorder.start()
        } catch (error: Exception) {
            releaseRecorder(recorder)
            file.delete()
            throw IOException("The microphone could not be started.", error)
        }

        mediaRecorder = recorder
        outputFile = file
        return file
    }

    @Synchronized
    fun stop(): File {
        val recorder = mediaRecorder
            ?: throw IllegalStateException("There is no active recording.")
        val file = outputFile
            ?: throw IllegalStateException("The recording file is unavailable.")
        var stopped = false

        try {
            recorder.stop()
            stopped = true
        } catch (error: RuntimeException) {
            throw IOException("The recording was too short or could not be finalized.", error)
        } finally {
            releaseRecorder(recorder)
            mediaRecorder = null
            outputFile = null
            if (!stopped) {
                file.delete()
            }
        }

        if (!file.isFile || file.length() == 0L) {
            file.delete()
            throw IOException("The recording did not contain audio.")
        }
        return file
    }

    @Synchronized
    fun cancel() {
        val recorder = mediaRecorder
        val file = outputFile
        mediaRecorder = null
        outputFile = null
        if (recorder != null) {
            releaseRecorder(recorder)
        }
        file?.delete()
    }

    @Suppress("DEPRECATION")
    private fun createMediaRecorder(): MediaRecorder {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(appContext)
        } else {
            MediaRecorder()
        }
    }

    private fun releaseRecorder(recorder: MediaRecorder) {
        try {
            recorder.reset()
        } catch (_: RuntimeException) {
            // The recorder may already be in an unrecoverable state.
        }
        try {
            recorder.release()
        } catch (_: RuntimeException) {
            // There is no useful recovery action after a release failure.
        }
    }

    private companion object {
        const val RECORDINGS_DIRECTORY = "recordings"
        const val AUDIO_BIT_RATE = 128_000
        const val AUDIO_SAMPLE_RATE = 44_100
    }
}
